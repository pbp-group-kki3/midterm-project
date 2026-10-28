from django.urls import path
from comparison.views import (
    compare_products,remove_product, save_comparison
)

app_name = "comparison"

urlpatterns = [
    path("", compare_products, name="compare_products"),
    path("remove/<str:barcode>/", remove_product, name="remove_product"),
    path("save/", save_comparison, name="save_comparison"),
]