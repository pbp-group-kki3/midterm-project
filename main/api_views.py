# change: new file for Checkpoint 1. The JSON API that the Flutter app talks to.
#
# This sits NEXT TO views.py, it doesn't replace anything: the website keeps using views.py exactly as before.
# Every view here reuses the same services and helpers as the website (search, grading, filters, prepare_card),
# so the app and the site always show the same products, grades and hearts.
from django.core.cache import cache                  # to check the "API is down" flag the services set
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from main.decorators import SEARCH_LIMIT, FAVORITE_LIMIT        # same limits as the website's @rate_limit
from main.forms import DiscoverFilterForm                       # same search + filter checks as the Discover page
from main.models import FavoriteProduct, ViewHistory
from main.serializers import ProductCardSerializer, FavoriteProductSerializer
from main.services.details import build_grade_rows, build_nutrition, nutrition_unit, clean_ingredients
from main.services.filters import passes_filters, best_grade_key
from main.services.openfoodfacts import (
    search_products, browse_products, get_product, get_alternatives,
    is_valid_barcode, is_stale, DOWN_KEY,
)
from main.views import prepare_card, saved_barcodes, clean_name   # reuse the website's helpers, no copy-paste
from profiles.services import get_preferences                    # Serafin's helper: the user's diet and allergies


API_DOWN_MESSAGE = "Open Food Facts isn't responding right now. Please try again in a minute."


# change: Flutter's CookieRequest logs in with the session cookie but can't send a CSRF token,
# so for the API we keep the session login and skip only the CSRF check (team guide, same class for every module)
class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


# change: DRF's own rate limit, so the app gets a 429 JSON answer (our @rate_limit decorator answers with an HTML page).
# Setting `rate` here means nothing has to be added to the shared settings.py.
# UserRateThrottle counts per user when logged in, per IP address when not
class SearchThrottle(UserRateThrottle):
    scope = "products_search"
    rate = f"{SEARCH_LIMIT}/min"        # 60 a minute, same as the website


class FavoriteThrottle(UserRateThrottle):
    scope = "products_favorite"
    rate = f"{FAVORITE_LIMIT}/min"      # 30 heart taps a minute, same as the website


# change: GET /api/products/?q=indomie&grade=A&label=halal&processing=not_ultra&avoid=milk&sort=grade
# Nothing typed (no q) -> popular products, like the Discover page before you search
@api_view(["GET"])
@throttle_classes([SearchThrottle])
def product_list(request):
    # the same Django form as the website: bad values (?grade=Z) are dropped, the text is cleaned, it's always valid
    form = DiscoverFilterForm(request.GET)
    form.is_valid()
    filters = form.cleaned_data
    q = filters["q"]

    results = search_products(q) if q else browse_products()
    if results is None:                                   # None = the API failed and we have no saved copy
        return Response({"detail": API_DOWN_MESSAGE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    prefs = get_preferences(request.user) if request.user.is_authenticated else None   # logged out: no chip
    saved = saved_barcodes(request)                                                     # for is_favorite
    products = [prepare_card(p, prefs, saved) for p in results]
    # filtering happens on the results we already have, no extra API call per filter (team rule)
    products = [
        p for p in products
        if passes_filters(p, filters["grade"], filters["label"], filters["processing"], filters["avoid"])
    ]
    if filters["sort"] == "grade":
        products.sort(key=best_grade_key, reverse=True)

    # no "show" / load more here: the app gets the whole list (max 24) and scrolls through it itself
    return Response({
        "query": q,
        "stale": is_stale(results),     # True = API down, these are results saved earlier (the app can show a note)
        "count": len(products),
        "results": ProductCardSerializer(products, many=True).data,   # many=True -> a list of cards
    })


# change: GET /api/products/<barcode>/ -> one product with the detail page's panels and up to 3 better alternatives
@api_view(["GET"])
@throttle_classes([SearchThrottle])
def product_detail(request, barcode):
    if not is_valid_barcode(barcode):                     # only digits can be a barcode, checked before any API call
        return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

    product = get_product(barcode)
    if product is None:
        # get_product gives None for both "doesn't exist" and "API down", the down flag tells them apart
        if cache.get(DOWN_KEY):
            return Response({"detail": API_DOWN_MESSAGE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

    prefs = get_preferences(request.user) if request.user.is_authenticated else None
    saved = saved_barcodes(request)
    prepare_card(product, prefs, saved)
    alternatives = [prepare_card(p, prefs, saved) for p in get_alternatives(product)]

    # same as the website: opening a product while logged in adds it to the user's history (Serafin's History page)
    if request.user.is_authenticated:
        ViewHistory.objects.update_or_create(
            user=request.user,
            barcode=barcode,
            defaults={"product_name": product.get("product_name") or ""},
        )

    data = ProductCardSerializer(product).data            # the card fields first...
    data.update({                                         # ...then the extra panels, built by the same helpers as the website
        "grade_breakdown": build_grade_rows(product),     # "How the grade is built" bars
        "nutrition": build_nutrition(product),
        "nutrition_unit": nutrition_unit(product),        # "per 100 g" or "per 100 ml"
        "ingredients": clean_ingredients(product),        # null when the API has none
        "alternatives": ProductCardSerializer(alternatives, many=True).data,
    })
    return Response(data)


# change: POST /api/products/<barcode>/favorite/ (body: product_name, optional) -> save or unsave, like the heart
@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])   # logged in through Flutter's CookieRequest
@permission_classes([IsAuthenticated])                       # logged out -> 403 JSON, never touches the database
@throttle_classes([FavoriteThrottle])
def toggle_favorite(request, barcode):
    if not is_valid_barcode(barcode):                        # never save a fake barcode
        return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

    # request.data reads both form data (CookieRequest.post) and JSON (CookieRequest.postJson)
    posted_name = clean_name(request.data.get("product_name", ""))   # no HTML tags, max 255, same as the website
    favorite = FavoriteProduct.objects.filter(user=request.user, barcode=barcode).first()

    if favorite:                                             # already saved -> remove it
        name = favorite.product_name or posted_name
        favorite.delete()
        return Response({
            "saved": False,
            "message": f"{name or 'This product'} was removed from your saved products.",
            "favorite": None,
        })

    favorite = FavoriteProduct.objects.create(user=request.user, barcode=barcode, product_name=posted_name)
    return Response(
        {
            "saved": True,
            "message": f"{posted_name or 'This product'} was added to your saved products.",
            "favorite": FavoriteProductSerializer(favorite).data,
        },
        status=status.HTTP_201_CREATED,                      # 201 = something new was created
    )
