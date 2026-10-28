from django.shortcuts import render, redirect
from django.http import HttpResponse
from main.services.openfoodfacts import search_products, get_product, get_alternatives # import search function + to call API
from main.services.grading import spoonfeed_grade, grade_value, NUTRI_POINTS, GREEN_POINTS,NOVA_POINTS # import gradings
from django.contrib.auth.decorators import login_required
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from main.models import FavoriteProduct, ViewHistory

# nutrition constant
NUTRIENTS = [
    ("Energy", "energy-kcal_100g", "kcal"),
    ("Fat", "fat_100g", "g"),
    ("Saturated fat", "saturated-fat_100g", "g"),
    ("Carbohydrates", "carbohydrates_100g", "g"),
    ("Sugars", "sugars_100g", "g"),
    ("Fiber", "fiber_100g", "g"),
    ("Protein", "proteins_100g", "g"),
    ("Salt", "salt_100g", "g"),
]

# preparation function
# adds what the product card needs = grade + 3 values
def prepare_card(p):
    p["spoonfeed"] = spoonfeed_grade(p)
    p["tiles"] = {
        "nutri" : grade_value(p.get("nutriscore_grade"), NUTRI_POINTS),
        "green": grade_value(p.get("ecoscore_grade"), GREEN_POINTS),
        "nova": grade_value(p.get("nova_group"), NOVA_POINTS),
    }
    return p

# main / product discovery page
def show_main(request):
    q = request.GET.get("q", "").strip()
    products = []
    error = False

    if q:
        results = search_products(q)
        if results is None:
            error = True
        else:
            products = [prepare_card(p) for p in results]   

    context = {"q": q, "products": products, "searched": bool(q), "error": error}
    return render(request, "main/main.html", context)

def product_detail(request, barcode):
    product = get_product(barcode)                           
    if product is None:
        return render(request, "main/product_detail.html", {"product": None})

    prepare_card(product)
    parts = product["spoonfeed"]["parts"]                   

    
    why = [
        {"label": "Nutrition", "points": parts.get("nutrition")},
        {"label": "Environment", "points": parts.get("environment")},
        {"label": "Processing", "points": parts.get("processing")},
    ]

    nutriments = product.get("nutriments") or {}
    nutrition = [
        {"label": label, "value": nutriments.get(key), "unit": unit}
        for label, key, unit in NUTRIENTS
    ]

    alternatives = [prepare_card(a) for a in get_alternatives(product)]   

    is_favorite = False
    if request.user.is_authenticated:                       
        ViewHistory.objects.update_or_create(                
            user=request.user,
            barcode=barcode,
            defaults={"product_name": product.get("product_name") or ""},   
        )
        is_favorite = FavoriteProduct.objects.filter(user=request.user, barcode=barcode).exists()

    context = {
        "product": product,
        "barcode": barcode,
        "why": why,
        "nutrition": nutrition,
        "alternatives": alternatives,
        "is_favorite": is_favorite,
    }
    return render(request, "main/product_detail.html", context)

# function : add to favorites action
@login_required # logged out -> sent to LOGIN_URL
@require_POST # GET (typing the URL) is refused
def toggle_favorite(request, barcode):
    favorite = FavoriteProduct.objects.filter(user=request.user, barcode=barcode).first()
    if favorite:
        favorite.delete() # if already saved -> remove
    else:
        FavoriteProduct.objects.create(
            user=request.user,
            barcode=barcode,
            product_name=request.POST.get("product_name", "")[:255],   # [:255] fits the field's max_length
        )

    # Go back to the page the heart was clicked on, but only if it's on OUR site (blocks open redirects)
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("main:product_detail", barcode=barcode)
