from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from meal_plan.constants import (
    ALLERGY_BADGES,
    DEFAULT_DIET,
    DIET_CHOICES,
    DIET_LABELS,
    HALAL_BADGE,
    MAX_DAYS,
    MIN_DAYS,
    SLOT_CHOICES,
    SLOT_ORDER,
)


class MealPlan(models.Model):
    TIMEFRAME_CHOICES = [
        ('day', 'Day'),
        ('week', 'Week'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meal_plans')
    name = models.CharField(max_length=60)
    date = models.DateField()
    timeframe = models.CharField(max_length=4, choices=TIMEFRAME_CHOICES)
    days = models.PositiveSmallIntegerField(validators=[MinValueValidator(MIN_DAYS), MaxValueValidator(MAX_DAYS)])
    diet = models.CharField(max_length=20, choices=DIET_CHOICES, default=DEFAULT_DIET)
    diets = models.JSONField(default=list, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    include_snack = models.BooleanField(default=False)
    calorie_goal = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return self.name

    @property
    def end_date(self):
        return self.date + timedelta(days=self.days - 1)

    @property
    def diet_keys(self):
        chosen = {key for key in self.diets or [] if isinstance(key, str)}
        if not chosen and self.diet != DEFAULT_DIET:
            chosen = {self.diet}
        return [key for key in DIET_LABELS if key != DEFAULT_DIET and key in chosen]

    @property
    def diet_labels(self):
        return [HALAL_BADGE if key == 'halal' else DIET_LABELS[key] for key in self.diet_keys]

    @property
    def diet_label(self):
        return ', '.join(self.diet_labels) or DIET_LABELS[DEFAULT_DIET]

    @property
    def calorie_label(self):
        return f'{self.calorie_goal:,} kcal/day'

    @property
    def days_label(self):
        return '1 day' if self.days == 1 else f'{self.days} days'

    @property
    def allergy_badges(self):
        return [ALLERGY_BADGES[key] for key in self.allergies if key in ALLERGY_BADGES]

    def date_for(self, day):
        return self.date + timedelta(days=day - 1)


class MealPlanEntry(models.Model):
    plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE, related_name='entries')
    day = models.PositiveSmallIntegerField(validators=[MinValueValidator(MIN_DAYS), MaxValueValidator(MAX_DAYS)])
    slot = models.CharField(max_length=10, choices=SLOT_CHOICES)
    recipe_id = models.PositiveIntegerField()

    class Meta:
        ordering = ['day', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['plan', 'day', 'slot'], name='meal_plan_one_recipe_per_slot'),
        ]
        verbose_name_plural = 'meal plan entries'

    def __str__(self):
        return f'{self.plan} · day {self.day} · {self.slot}'

    @property
    def slot_position(self):
        return SLOT_ORDER.index(self.slot) if self.slot in SLOT_ORDER else len(SLOT_ORDER)

    @property
    def date(self):
        return self.plan.date_for(self.day)
