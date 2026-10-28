from django.shortcuts import render
from django.http import HttpResponse
from main.services.openfoodfacts import search_products # import search function + to call API
from main.services.grading import spoonfeed_grade, grade_value, NUTRI_POINTS, GREEN_POINTS,NOVA_POINTS # import gradings

# main / product discovery page
def show_main(request):
    q = request.GET.get("q","").strip() # the query / question will be put after the ?q - strips extra line
    products = []
    error = False

    if q:
        results = search_products(q)
        if results is None:
            error = True
        else:
            products = results

    for p in products:
        p["spoonfeed"] = spoonfeed_grade(p)
        p["tiles"] = {
            "nutri" : grade_value(p.get("nutriscore_grade"), NUTRI_POINTS),
            "green" : grade_value(p.get("ecoscore_grade"), GREEN_POINTS),
            "nova" : grade_value(p.get("nova_group"), NOVA_POINTS),
        }

    context = {
        "q" : q, # used to write "results for q" in search bar
        "products" : products,
        "searched" : bool(q), # true when a search is made
        "error" : error,
    }
    return render(request,"main/main.html", context)
