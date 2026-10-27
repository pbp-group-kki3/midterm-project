from django.shortcuts import render
from main.services.openfoodfacts import get_product

# Create your views here.
def compare_products(request):
    selected_barcodes = request.session.get("compare", [])
    barcodes = list(dict.fromkeys(selected_barcodes))[:3]

    products = []
    unavailable_barcodes = []

    for barcode in barcodes:
        product = get_product(barcode)

        if product:
            products.append(product)
        else:
            unavailable_barcodes.append(barcode)

    context = {
        "barcodes": barcodes,
        "unavailable_barcodes": unavailable_barcodes,
    }
    return render(request, "comparison/compare.html", context)