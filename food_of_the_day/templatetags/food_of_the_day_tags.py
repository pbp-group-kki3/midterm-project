from django import template
from django.utils import timezone
from food_of_the_day.models import MealOfTheDay
from food_of_the_day.views import _prepare_meal_context
from food_of_the_day.services import get_todays_meal  # change: shared helper

register = template.Library()


@register.inclusion_tag('food_of_the_day/components/slide.html', takes_context=True)
def meal_of_the_day_slide(context):
    """
    Renders the Meal of the Day card for home page carousel or embed.
    If no entry exists for today, meal is None and the component can be cleanly skipped.
    """
    request = context.get('request')
    today_meal = get_todays_meal()  # change: the homepage slide is never empty now
    data = _prepare_meal_context(today_meal, request)
    data['request'] = request
    data['user'] = context.get('user')
    return data
