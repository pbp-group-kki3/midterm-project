"""
Models for the Meal of the Day (food_of_the_day) module.

Architecture Overview:
1. MealOfTheDay: Represents the daily recommendation schedule, binding each calendar date
   to a verified Spoonacular recipe ID.
2. MealComment: User-generated community comments and discussions attached to a featured meal.
3. SavedMeal: Persistent bookmark model using an immutable 'snapshot' architecture.
   When a user bookmarks a recipe, a point-in-time JSON copy of the recipe (ingredients,
   instructions, nutrition) is stored so the bookmark remains permanently accessible
   even if external APIs fail or meal schedules are altered.
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MinLengthValidator


class MealOfTheDay(models.Model):
    """
    Stores which recipe is featured on any given calendar date.
    
    Key Constraints:
    - `date`: Unique constraint ensures only one official recipe is featured per day.
    - `recipe_id`: Must be a positive integer matching a valid Spoonacular recipe ID.
    """
    date = models.DateField(
        unique=True,
        help_text="The calendar date this meal is featured on."
    )
    recipe_id = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Unique Spoonacular recipe identifier."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    #@property 
    #def average_rating(self):
        #return self.comments.aggregate(models.Avg('rating'))['rating__avg'] or 0

    #@property
    #def total_saves(self):
        #return self.saved_by_users.count()

    class Meta:
        verbose_name = "Meal of the Day"
        verbose_name_plural = "Meals of the Day"
        ordering = ['-date']  # Most recent featured meals appear first by default

    def __str__(self):
        return f"Meal of the Day for {self.date} (Recipe ID: {self.recipe_id})"


class MealComment(models.Model):
    """
    Community discussion comments posted on a featured meal.
    
    Key Constraints:
    - User authentication required: foreign key links comment to the author.
    - Cascade delete: if the parent meal is deleted, associated comments are cleaned up.
    - Length limits: enforces minimum 2 characters and maximum 1000 characters.
    """
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
        validators=[MinLengthValidator(2)],
        help_text="User comment content (between 2 and 1000 characters)."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_text(self):
        txt = self.text
        splittext = txt.split()
        return len(splittext)

    # rating = models.PositiveSmallIntegerField(
    #     default=5,
    #     validators=[MinValueValidator(1), MaxValueValidator(5)]
    # )

    class Meta:
        verbose_name = "Meal Comment"
        verbose_name_plural = "Meal Comments"
        ordering = ['-created_at']  # Chronological descending order (newest on top)

    def __str__(self):
        meal_date = getattr(self.meal, 'date', 'unknown')
        return f"Comment by {self.user} on {meal_date}: {self.text[:30]}"


class SavedMeal(models.Model):
    """
    User bookmark collection for recipes with an immutable point-in-time snapshot.
    
    Why Snapshot Data?
    - Decouples saved items from external third-party API availability (Spoonacular).
    - If Spoonacular hits rate limits, downtime, or alters recipe details, the user's
      bookmarked version remains 100% intact and fast to render from the local database.
    
    Why on_delete=models.SET_NULL for `meal`?
    - If an administrator wipes or re-seeds the MealOfTheDay schedule, the user's saved
      recipes are NEVER deleted. They gracefully decouple and remain in the user's profile.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_meals',
    )
    meal = models.ForeignKey(
        MealOfTheDay,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='saved_by_users',
    )
    recipe_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Cached Spoonacular recipe ID for standalone lookups."
    )
    recipe_title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Human-readable recipe title saved at bookmark time."
    )

    # Immutable JSON snapshot of the full recipe details (ingredients, instructions, nutrition)
    snapshot_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Frozen JSON snapshot of recipe details captured at the time of bookmarking."
    )

    # notes = models.TextField(blank=True, default='', help_text="Personal cooking notes.")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Saved Meal"
        verbose_name_plural = "Saved Meals"
        ordering = ['-created_at']
        constraints = [
            # Prevent duplicate bookmarks: a user can only save a specific scheduled meal once
            models.UniqueConstraint(
                fields=['user', 'meal'],
                condition=models.Q(meal__isnull=False),
                name='unique_saved_meal_per_user',
            ),
        ]

    def __str__(self):
        return f"{self.user.username} saved {self.recipe_title or self.meal}"

