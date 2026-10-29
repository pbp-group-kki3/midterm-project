from django.contrib import admin
from food_of_the_day.models import MealOfTheDay, MealComment, SavedMeal


@admin.register(MealOfTheDay)
class MealOfTheDayAdmin(admin.ModelAdmin):
    list_display = ('date', 'recipe_id', 'created_at')
    list_filter = ('date',)
    search_fields = ('recipe_id',)
    ordering = ('-date',)


@admin.register(MealComment)
class MealCommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'meal', 'created_at', 'short_text')
    list_filter = ('created_at', 'meal__date')
    search_fields = ('user__username', 'text')
    ordering = ('-created_at',)

    def short_text(self, obj):
        return obj.text[:50] + ("..." if len(obj.text) > 50 else "")
    short_text.short_description = "Comment"


@admin.register(SavedMeal)
class SavedMealAdmin(admin.ModelAdmin):
    list_display = ('user', 'meal', 'recipe_title', 'created_at')
    list_filter = ('created_at', 'meal__date')
    search_fields = ('user__username', 'recipe_title', 'meal__recipe_id')
    ordering = ('-created_at',)

