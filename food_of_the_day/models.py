from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MinLengthValidator


class MealOfTheDay(models.Model):
    date = models.DateField(unique=True, help_text="The date this meal is featured")
    recipe_id = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Spoonacular recipe ID"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Meal of the Day"
        verbose_name_plural = "Meals of the Day"
        ordering = ['-date']

    def __str__(self):
        return f"Meal of the Day for {self.date} (Recipe ID: {self.recipe_id})"


class MealComment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='meal_comments'
    )
    meal = models.ForeignKey(
        MealOfTheDay,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    text = models.TextField(
        max_length=1000,
        validators=[MinLengthValidator(2)]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Meal Comment"
        verbose_name_plural = "Meal Comments"
        ordering = ['-created_at']

    def __str__(self):
        meal_date = getattr(self.meal, 'date', 'unknown')
        return f"Comment by {self.user} on {meal_date}: {self.text[:30]}"


class SavedMeal(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_meals',
    )
    # SET_NULL preserves user bookmarks even if an admin clears or changes the meal schedule
    meal = models.ForeignKey(
        MealOfTheDay,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='saved_by_users',
    )
    recipe_id = models.IntegerField(null=True, blank=True)
    recipe_title = models.CharField(max_length=255, blank=True)

    # Immutable point-in-time snapshot of the recipe at bookmark time
    snapshot_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Saved Meal"
        verbose_name_plural = "Saved Meals"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'meal'],
                condition=models.Q(meal__isnull=False),
                name='unique_saved_meal_per_user',
            ),
        ]

    def __str__(self):
        return f"{self.user.username} saved {self.recipe_title or self.meal}"

