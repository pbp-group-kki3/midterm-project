from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.urls import reverse
from main.services.openfoodfacts import get_product
from main.services.grading import spoonfeed_grade

from comparison.services import (
    build_label_rows,
    build_score_rows,
    build_nutrition_rows,
    normalize_grade,
    normalize_nova,
)
from comparison.forms import SavedComparisonForm
from comparison.models import SavedComparison
# Create your views here.
@require_GET
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

    # SAVE COMPARISON
    can_save = (
        2 <= len(barcodes) <= 3
        and len(products) == len(barcodes)
        and all(
            isinstance(barcode, str)
            and barcode.isascii()
            and barcode.isdigit()
            for barcode in barcodes
        )
    )
    is_saved = False

    if request.user.is_authenticated and 2 <= len(barcodes) <= 3:
        is_saved = SavedComparison.objects.filter(
            user=request.user,
            barcodes=barcodes,
        ).exists()

    pending_save = request.session.pop("comparison_save_errors", None)

    if pending_save:
        save_form = SavedComparisonForm(pending_save["data"])
        save_form.is_valid()

        for error in pending_save["non_field_errors"]:
            save_form.add_error(None, error)
    else:
        save_form = SavedComparisonForm(
            initial={
                "selection": ",".join(barcodes),
            }
        )

    context = {
        "products": products,
        "unavailable_barcodes": unavailable_barcodes,
        "nutrition_rows": nutrition_rows, # label, nilai, and Better indicator
        "comparison_sections": comparison_sections,
        "show_add_product": show_add_product,
        "show_compare_panel": bool(products) or show_add_product,
        "table_column_count": display_column_count + 1,
        "save_form": save_form,
        "can_save": can_save,
        "open_save_dialog": save_form.is_bound,
        "save_login_url": redirect_to_login(reverse("comparison:compare_products")).url,
        "is_saved": is_saved,
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

        # Toast notification implementation:
        messages.success(request, "Product removed from comparison.")
    else:
        messages.warning(request, "This product is no longer in your comparison.")

    return redirect("comparison:compare_products")

@require_POST
def save_comparison(request):
    if not request.user.is_authenticated:
        return redirect_to_login(
            reverse("comparison:compare_products")
        )

    selected_barcodes = request.session.get("compare", [])
    barcodes = list(dict.fromkeys(selected_barcodes))[:3]

    save_form = SavedComparisonForm(request.POST)
    form_is_valid = save_form.is_valid()

    valid_selection = (
        2 <= len(barcodes) <= 3
        and all(
            isinstance(barcode, str)
            and barcode.isascii()
            and barcode.isdigit()
            for barcode in barcodes
        )
    )

    if not valid_selection:
        save_form.add_error(
            None,
            "Select two or three products before saving.",
        )
    elif (
        form_is_valid
        and save_form.cleaned_data["selection"] != ",".join(barcodes)
    ):
        save_form.add_error(
            None,
            "Your product selection has changed. "
            "Close this form and reload the page before saving.",
        )
    elif form_is_valid:
        products_available = all(
            get_product(barcode)
            for barcode in barcodes
        )

        if not products_available:
            save_form.add_error(
                None,
                "Some selected products could not be loaded. "
                "Please try again later.",
            )

    if save_form.errors:
        request.session["comparison_save_errors"] = {
            "data": {
                "name": request.POST.get("name", ""),
                "notes": request.POST.get("notes", ""),
                "selection": request.POST.get("selection", ""),
            },
            "non_field_errors": list(save_form.non_field_errors()),
        }

        return redirect("comparison:compare_products")

    already_saved = SavedComparison.objects.filter(user=request.user, barcodes=barcodes).exists()

    if already_saved:
        request.session.pop("comparison_save_errors", None)

        messages.info(
            request,
            "This product lineup is already saved.",
        )

        return redirect("comparison:compare_products")

    saved_comparison = save_form.save(commit=False)
    saved_comparison.user = request.user
    saved_comparison.barcodes = list(barcodes)
    saved_comparison.save()

    request.session.pop("comparison_save_errors", None)

    messages.success(
        request,
        "Comparison saved successfully.",
    )

    return redirect("comparison:compare_products")