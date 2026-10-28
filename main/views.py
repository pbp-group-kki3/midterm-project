from django.shortcuts import render, redirect
from django.contrib import messages # one-time notes like "Remove one to add another"
from django.http import HttpResponse
from main.services.openfoodfacts import search_products, browse_products, get_product, get_alternatives # import search function + to call API
from main.services.grading import spoonfeed_grade, grade_value, NUTRI_POINTS, GREEN_POINTS,NOVA_POINTS # import gradings
from main.services.filters import passes_filters, best_grade_key, preference_fit
from profiles.services import get_preferences # Serafin's helper: the user's diet and allergies # filters for the search results
from urllib.parse import urlencode # builds ?q=... safely
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

# Tags on a card (Figma: up to 2 slots, read from labels_tags). (tag, text, badge style)
TAG_RULES = [
    ("en:halal", "Halal", "badge-success"),
    ("en:organic", "Organic", "badge-success"),
    ("en:no-preservatives", "No preservatives", ""),
]

# Options in the filter panel (Figma "SF / Filter panel")
GRADE_OPTIONS = ["A", "B", "C", "D", "E"]
LABEL_OPTIONS = [("halal", "Halal"), ("vegetarian", "Vegetarian"), ("vegan", "Vegan"), ("organic", "Organic")]
ALLERGEN_OPTIONS = [("milk", "Milk"), ("peanuts", "Peanuts"), ("gluten", "Gluten"), ("soy", "Soy")]

# Quick filter chips under the search bar (Figma): (text, URL key, values it switches on/off)
QUICK_CHIPS = [
    ("Halal", "label", ["halal"]),
    ("Grade A\u2013B", "grade", ["A", "B"]),
    ("Not ultra-processed", "processing", ["not_ultra"]),
    ("No palm oil", "label", ["palm_oil_free"]),
    ("Vegan", "label", ["vegan"]),
]

PAGE_STEP = 6   # cards shown at first, and how many more "Load more" adds (Figma shows 6)


# preparation function
# adds what the product card needs = grade + 3 tile values + tags
def prepare_card(p, prefs=None):
    p["spoonfeed"] = spoonfeed_grade(p)
    p["fit"] = preference_fit(p, prefs)   # "Fits your preferences" chip, None when logged out / no preferences
    p["tiles"] = {
        "nutri" : grade_value(p.get("nutriscore_grade"), NUTRI_POINTS),
        "green": grade_value(p.get("ecoscore_grade"), GREEN_POINTS),
        "nova": grade_value(p.get("nova_group"), NOVA_POINTS),
    }
    labels = p.get("labels_tags") or []
    p["tags"] = [
        {"text": text, "style": style}
        for tag, text, style in TAG_RULES
        if tag in labels
    ][:2]   # Figma card has 2 tag slots
    return p


# helper : the current URL with some values switched on or off (used by the quick chips)
# returns (url, is_on_now)
def toggled_url(request, key, values):
    params = request.GET.copy()          # QueryDict copy we can change (request.GET itself is read-only)
    params.pop("show", None)             # a new filter starts again from the first 6 cards
    current = params.getlist(key)
    is_on = all(v in current for v in values)
    if is_on:
        current = [v for v in current if v not in values]                  # switch off
    else:
        current = current + [v for v in values if v not in current]        # switch on
    params.setlist(key, current)
    return "?" + params.urlencode(), is_on



COMPARE_MAX = 3   # agreed with Alyssa: her page reads up to 3 barcodes from request.session["compare"]


# helper : what the compare tray at the bottom needs, read from the session (no API call)
def compare_tray(request):
    barcodes = request.session.get("compare", [])          # shared with Alyssa's module
    info = request.session.get("compare_info", {})         # our own: name + grade per barcode, for the tray
    items = [
        {
            "barcode": code,
            "name": info.get(code, {}).get("name") or code,  # fall back to the barcode if we have no name
            "grade": info.get(code, {}).get("grade", "?"),
        }
        for code in barcodes
    ]
    return {
        "compare_items": items,
        "compare_count": len(items),
        "compare_empty_slots": range(COMPARE_MAX - len(items)),   # the dashed "+ Add a product" boxes
        "compare_max": COMPARE_MAX,
        "can_compare": len(items) >= 2,                     # Figma: "Compare now" is faded until 2 are picked
        "compare_barcodes": barcodes,
    }

# main / product discovery page: search + filters + sort + load more
def show_main(request):
    q = request.GET.get("q", "").strip()
    grades = request.GET.getlist("grade")              # e.g. ["A", "B"]  (getlist: a key can repeat)
    labels = request.GET.getlist("label")              # e.g. ["halal"]
    processing = request.GET.get("processing", "any")  # "not_ultra" or "any"
    avoid = request.GET.getlist("avoid")               # e.g. ["milk"]
    sort = request.GET.get("sort", "")                 # "grade" = best grade first, "" = API order
    try:
        show = max(PAGE_STEP, int(request.GET.get("show", PAGE_STEP)))   # how many cards to show
    except ValueError:                                 # someone typed ?show=abc
        show = PAGE_STEP

    products = []
    error = False
    prefs = get_preferences(request.user) if request.user.is_authenticated else None   # logged out: no chip
    results = search_products(q) if q else browse_products()   # nothing typed: show popular products
    if results is None:
        error = True
    else:
        products = [prepare_card(p, prefs) for p in results]
        # filter the cached results in Python: no extra API call per filter (team rule)
        products = [p for p in products if passes_filters(p, grades, labels, processing, avoid)]
        if sort == "grade":
            products.sort(key=best_grade_key, reverse=True)

    # quick chips: each one knows its link and whether it's on
    quick_chips = []
    for text, key, values in QUICK_CHIPS:
        url, is_on = toggled_url(request, key, values)
        quick_chips.append({"text": text, "url": url, "selected": is_on})

    # sort button: switches between best grade and the API's order
    sort_params = request.GET.copy()
    sort_params.pop("show", None)
    if sort == "grade":
        sort_params.pop("sort", None)
    else:
        sort_params["sort"] = "grade"

    # load more: same URL with 6 more cards
    more_params = request.GET.copy()
    more_params["show"] = show + PAGE_STEP

    context = {
        "q": q,
        "searched": bool(q),
        "error": error,
        "products": products[:show],                   # only the cards to show now
        "total": len(products),                        # for "6 results for ..."
        "has_more": len(products) > show,
        "more_url": "?" + more_params.urlencode(),
        "quick_chips": quick_chips,
        "sort": sort,
        "sort_url": "?" + sort_params.urlencode(),
        "filter_count": (1 if grades else 0) + len(labels) + (1 if processing == "not_ultra" else 0) + len(avoid),
        "clear_url": "?" + urlencode({"q": q}),         # same search, no filters
        # filter panel: every option with whether it's ticked
        "grade_options": [{"value": g, "checked": g in grades} for g in GRADE_OPTIONS],
        "label_options": [{"value": v, "text": t, "checked": v in labels} for v, t in LABEL_OPTIONS],
        "allergen_options": [{"value": v, "text": t, "checked": v in avoid} for v, t in ALLERGEN_OPTIONS],
        "processing": processing,
    }
    context.update(compare_tray(request))                  # the compare tray at the bottom
    return render(request, "main/main.html", context)

def product_detail(request, barcode):
    product = get_product(barcode)                           
    if product is None:
        return render(request, "main/product_detail.html", {"product": None})

    prefs = get_preferences(request.user) if request.user.is_authenticated else None
    prepare_card(product, prefs)
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

    alternatives = [prepare_card(a, prefs) for a in get_alternatives(product)]   

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
    context.update(compare_tray(request))
    return render(request, "main/product_detail.html", context)

# function : add to favorites action
@login_required(login_url="login")   # login page by its URL name (Profile module), works even if settings.LOGIN_URL is outdated
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


# helper : go back to the page the button was on, but only if it's on OUR site (blocks open redirects)
def back_to(request, fallback="main:show_main"):
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback)


# "+ Compare": put a product in the compare tray (session). Logged out -> login page (team doc + Figma)
@login_required(login_url="login")   # login page by its URL name (Profile module), works even if settings.LOGIN_URL is outdated
@require_POST
def add_to_compare(request, barcode):
    barcodes = request.session.get("compare", [])
    if barcode in barcodes:
        messages.info(request, "This product is already in your comparison.")
    elif len(barcodes) >= COMPARE_MAX:
        messages.warning(request, "Remove one to add another.")   # wording from the team doc
    else:
        barcodes.append(barcode)
        request.session["compare"] = barcodes               # assigning again tells Django the session changed
        info = request.session.get("compare_info", {})
        info[barcode] = {
            "name": request.POST.get("product_name", "")[:255],
            "grade": request.POST.get("grade", "?")[:1],    # one letter, A-E or ?
        }
        request.session["compare_info"] = info
    return back_to(request)


# The x on a tray item: take it out of the comparison and stay on this page
@login_required(login_url="login")   # login page by its URL name (Profile module), works even if settings.LOGIN_URL is outdated
@require_POST
def remove_from_compare(request, barcode):
    request.session["compare"] = [b for b in request.session.get("compare", []) if b != barcode]
    info = request.session.get("compare_info", {})
    info.pop(barcode, None)
    request.session["compare_info"] = info
    return back_to(request)

