from django.urls import path
from comparison.views import (
    compare_products,remove_product
)

app_name = "comparison"

urlpatterns = [
    path("", compare_products, name="compare_products"),
    path("remove/<str:barcode>/", remove_product, name="remove_product"),
]