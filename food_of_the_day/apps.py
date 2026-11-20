"""
Django application configuration for the Meal of the Day module.
"""

from django.apps import AppConfig


class FoodOfTheDayConfig(AppConfig):
    """
    Configures app name, default primary key field type,
    and human-friendly verbose name for Django admin.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'food_of_the_day'
    verbose_name = 'Meal of the Day'
