from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.urls import reverse
from main.services.openfoodfacts import get_product
from django.http import JsonResponse

from comparison.services import (
    build_comparison_sections,
    build_nutrition_rows,
    load_comparison_products,
)
from comparison.forms import SavedComparisonForm
from comparison.models import SavedComparison
# Create your views here.
@require_GET
def compare_products(request, saved_comparison=None):
    # Display saved lineups without replacing the active session selection.
    viewing_saved = saved_comparison is not None
    selected_barcodes = saved_comparison.barcodes if viewing_saved else request.session.get("compare", [])
    barcodes = list(dict.fromkeys(selected_barcodes))[:3]

    products, unavailable_barcodes = load_comparison_products(barcodes)

    if unavailable_barcodes:
        messages.warning(
            request,
            "Some selected products could not be loaded. "
            "Please try again later.",
        )

    nutrition_rows = build_nutrition_rows(products)
    comparison_sections = build_comparison_sections(
        products,
        nutrition_rows,
    )

    has_removed = request.session.get("compare_has_removed", False)
    show_add_product = not viewing_saved and has_removed and len(barcodes) < 3
    display_column_count = len(products) + int(show_add_product)

    can_save = (
        not viewing_saved
        and 2 <= len(barcodes) <= 3
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

    save_form = SavedComparisonForm(
        initial={
            "selection": ",".join(barcodes),
        }
    )

    context = {
        "products": products,
        "viewing_saved": viewing_saved,
        "unavailable_barcodes": unavailable_barcodes,
        "nutrition_rows": nutrition_rows, # label, nilai, and Better indicator
        "comparison_sections": comparison_sections,
        "show_add_product": show_add_product,
        "show_compare_panel": bool(products) or show_add_product,
        "table_column_count": display_column_count + 1,
        "save_form": save_form,
        "can_save": can_save,
        "open_save_dialog": False,
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

        compare_info = request.session.get("compare_info", {}).copy()
        compare_info.pop(barcode, None)
        request.session["compare_info"] = compare_info

        request.session["compare_has_removed"] = True

        # Toast notification implementation:
        messages.success(request, "Product removed from comparison.")
    else:
        messages.warning(request, "This product is no longer in your comparison.")

    return redirect("comparison:compare_products")

@require_POST
def save_comparison(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "ok": False,
                "message": "Please log in before saving this comparison.",
                "login_url": redirect_to_login(reverse("comparison:compare_products")).url,
            },
            status=401,
        )

    selected_barcodes = request.session.get("compare", [])

    valid_selection = (
        isinstance(selected_barcodes, list)
        and all(
            isinstance(barcode, str)
            and barcode.isascii()
            and barcode.isdigit()
            for barcode in selected_barcodes
        )
    )

    barcodes = list(dict.fromkeys(selected_barcodes) if valid_selection else [])

    save_form = SavedComparisonForm(request.POST)
    form_is_valid = save_form.is_valid()

    if not 2 <= len(barcodes) <= 3:
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
            "Reload the page before saving.",
        )

    if save_form.errors:
        return JsonResponse(
            {
                "ok": False,
                "errors": save_form.errors.get_json_data(),
            },
            status=400,
        )

    already_saved = SavedComparison.objects.filter(user=request.user, barcodes=barcodes).exists()

    if already_saved:
        return JsonResponse(
            {
                "ok": True,
                "already_saved": True,
                "message": "This comparison is already saved to your profile.",
            }
        )

    products_available = True

    for barcode in barcodes:
        product = get_product(barcode)

        if not isinstance(product, dict) or not product:
            products_available = False
            break

    if not products_available:
        save_form.add_error(
            None,
            "Some selected products could not be loaded."
            "Please try again later.",
        )

        return JsonResponse(
            {
                "ok": False,
                "errors": save_form.errors.get_json_data(),
            },
            status=400,
        )
    
    saved_comparison = save_form.save(commit=False)
    saved_comparison.user = request.user
    saved_comparison.barcodes = barcodes
    saved_comparison.save()

    request.session.pop("comparison_save_errors", None)

    return JsonResponse(
        {
            "ok": True,
            "already_saved": False,
            "message": "Comparison saved to your profile.",
        },
        status=201,
    )
