from django.urls import path
from main.views import show_main, product_detail, toggle_favorite, add_to_compare, remove_from_compare

app_name = 'main'

urlpatterns = [
    path('', show_main, name='show_main'),
    path('product/<str:barcode>/', product_detail, name='product_detail'),         
    path('favorite/<str:barcode>/', toggle_favorite, name='toggle_favorite'), 
    path('tray/add/<str:barcode>/', add_to_compare, name='add_to_compare'),           # POST: + Compare
    path('tray/remove/<str:barcode>/', remove_from_compare, name='remove_from_compare'),  # POST: x in the tray
]
