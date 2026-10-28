from django.contrib import admin
from main.models import FavoriteProduct, ViewHistory

# Register your models here.

# show favorites in /admin/ as table
@admin.register(FavoriteProduct)
class FavoriteProductAdmin(admin.ModelAdmin):
    list_display = ("user","product_name","barcode","created_at")
    search_fields = ("product_name","barcode")

# show view history in /admin/
@admin.register(ViewHistory)
class ViewHistoryAdmin(admin.ModelAdmin):
    list_display = ("user","product_name","barcode","viewed_at")
    search_fields = ("product_name","barcode")

