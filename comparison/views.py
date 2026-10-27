from django.shortcuts import render
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from main.services.openfoodfacts import get_product
from main.services.grading import spoonfeed_grade
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
            product["compare_barcode"] = barcode

            grading = spoonfeed_grade(product)
            product["compare_grade"] = grading["grade"]
            product["compare_score"] = grading["score"]

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

    comparison_sections = [
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
    ]

    has_removed = request.session.get("compare_has_removed", False)
    show_add_product = has_removed and len(barcodes) < 3

    display_column_count = len(products) + int(show_add_product)

    context = {
        "products": products,
        "unavailable_barcodes": unavailable_barcodes,
        "nutrition_rows": nutrition_rows,
        "nutrition_rows": nutrition_rows, # label, nilai, and Better indicator
        "comparison_sections": comparison_sections,
        "show_add_product": show_add_product,
        "show_compare_panel": bool(products) or show_add_product,
        "table_column_count": display_column_count + 1,
    }
    return render(request, "comparison/compare.html", context)

@require_POST
def remove_product(request, barcode):
    selected_barcodes = request.session.get("compare", [])

    if barcode in selected_barcodes:
        request.session["compare"] = [
            selected_barcode
            for selected_barcode in selected_barcodes
            if selected_barcode != barcode
        ]

        request.session["compare_has_removed"] = True

    return redirect("comparison:compare_products")