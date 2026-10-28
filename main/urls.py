from django.urls import path
from main.views import show_main, product_detail, toggle_favorite

app_name = 'main'

urlpatterns = [
    path('', show_main, name='show_main'),
    path('product/<str:barcode>/', product_detail, name='product_detail'),         
    path('favorite/<str:barcode>/', toggle_favorite, name='toggle_favorite'), 
]
