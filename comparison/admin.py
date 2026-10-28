from django.contrib import admin
from .models import SavedComparison

# Register your models here.
@admin.register(SavedComparison)
class SavedComparisonAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "user__username"]
    readonly_fields = ["created_at"]