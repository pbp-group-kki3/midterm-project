from django.shortcuts import render

# Create your views here.
def compare_products(request):
    barcodes = request.session.get("compare", [])

    context = {
        "barcodes": barcodes,
    }
    return render(request, "comparison/compare.html", context)