from django.urls import path
from comparison.views import (
    compare_products,
)

app_name = "comparison"

urlpatterns = [
    path("", compare_products, name="compare_products"),
]