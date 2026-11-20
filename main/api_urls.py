# change: new file for Checkpoint 1. The JSON API paths for Product Discovery.
# midterm_project/urls.py puts these under /api/products/ (the commented line there),
# so '' here becomes /api/products/ and '<str:barcode>/' becomes /api/products/<barcode>/
from django.urls import path

from main import api_views

urlpatterns = [
    path('', api_views.product_list, name='api_product_list'),                                # GET: search / browse + filters
    path('<str:barcode>/', api_views.product_detail, name='api_product_detail'),               # GET: one product + alternatives
    path('<str:barcode>/favorite/', api_views.toggle_favorite, name='api_product_favorite'),   # POST: save / unsave (login needed)
]
