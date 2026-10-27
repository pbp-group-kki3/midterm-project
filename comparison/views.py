from django.shortcuts import render
from main.services.openfoodfacts import get_product
from comparison.services import (
    build_label_rows,
    build_score_rows,
    build_nutrition_rows,
    normalize_grade,
    normalize_nova,
)
# Create your views here.
def compare_products(request):
    selected_barcodes = request.session.get("compare", [])
    barcodes = list(dict.fromkeys(selected_barcodes))[:3]

    products = []
    unavailable_barcodes = []

    for barcode in barcodes:
        product = get_product(barcode)

        if product:
            product = product.copy()

            product["compare_nutri"] = normalize_grade(
                product.get("nutriscore_grade")
            )
            product["compare_green"] = normalize_grade(
                product.get("ecoscore_grade")
            )
            product["compare_nova"] = normalize_nova(
                product.get("nova_group")
            )

            products.append(product)
        else:
            unavailable_barcodes.append(barcode)

    nutrition_rows = build_nutrition_rows(products)
    
    context = {
        "products": products,
        "unavailable_barcodes": unavailable_barcodes,
        "nutrition_rows": nutrition_rows,
        "nutrition_rows": build_nutrition_rows(products), # label, nilai, and Better indicator
        "comparison_sections": [
            {
                "title": "Scores",
                "rows": build_score_rows(products),
            },
            {
                "title": "Nutrition per 100 g/ml",
                "rows": nutrition_rows,
            },
            {
                "title": "Labels and allergens",
                "rows": build_label_rows(products),
            },
        ],
    }
    return render(request, "comparison/compare.html", context)