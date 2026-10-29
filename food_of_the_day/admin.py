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
    list_display = ('user', 'meal', 'recipe_id', 'recipe_title', 'has_snapshot', 'created_at')
    list_filter = ('created_at', 'meal__date')
    search_fields = ('user__username', 'recipe_title', 'recipe_id')
    readonly_fields = ('created_at', 'snapshot_data')
    ordering = ('-created_at',)

    def has_snapshot(self, obj):
        return bool(obj.snapshot_data)
    has_snapshot.boolean = True
    has_snapshot.short_description = "Snapshot"

