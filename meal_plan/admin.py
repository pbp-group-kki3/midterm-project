from django.contrib import admin

from meal_plan.models import MealPlan, MealPlanEntry


class MealPlanEntryInline(admin.TabularInline):
    model = MealPlanEntry
    extra = 0
    fields = ['day', 'slot', 'recipe_id']
    ordering = ['day', 'pk']


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'date', 'days', 'diet', 'calorie_goal', 'created_at']
    list_filter = ['diet', 'timeframe', 'include_snack']
    search_fields = ['name', 'user__username']
    date_hierarchy = 'date'
    inlines = [MealPlanEntryInline]
