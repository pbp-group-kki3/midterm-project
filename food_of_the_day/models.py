from django.db import models
from django.conf import settings


class MealOfTheDay(models.Model):
    date = models.DateField(unique=True, help_text="The date this meal is featured")
    recipe_id = models.IntegerField(help_text="Spoonacular recipe ID")
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
    text = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Meal Comment"
        verbose_name_plural = "Meal Comments"
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.user} on {self.meal.date}: {self.text[:30]}"
