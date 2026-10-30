from django.urls import path
from comparison.views import (
    compare_products, remove_product, save_comparison, edit_saved_comparison, remove_saved_comparison,
)

app_name = "comparison"

urlpatterns = [
    path("", compare_products, name="compare_products"),
    path("remove/<str:barcode>/", remove_product, name="remove_product"),
    path("save/", save_comparison, name="save_comparison"),
    path("saved/<int:pk>/edit/", edit_saved_comparison, name="edit_saved_comparison"),
    path("saved/<int:pk>/remove/", remove_saved_comparison, name="remove_saved_comparison"),
]