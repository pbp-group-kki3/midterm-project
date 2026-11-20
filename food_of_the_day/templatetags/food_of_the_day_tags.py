"""
Custom template tags for the Meal of the Day module.

Usage:
  {% load food_of_the_day_tags %}
  {% meal_of_the_day_slide %}

Allows other apps (like the 'main' discover homepage) to embed the live Meal of the Day
hero slide without duplicate view code or database querying.
"""

from django import template
from food_of_the_day.views import _prepare_meal_context
from food_of_the_day.services import get_todays_meal

register = template.Library()


@register.inclusion_tag('food_of_the_day/components/slide.html', takes_context=True)
def meal_of_the_day_slide(context):
    """
    Renders the Meal of the Day hero card for homepage carousel integration.
    Automatically fetches or creates today's meal, loads Spoonacular metrics,
    and passes the current user/request context to the template.
    """
    request = context.get('request')
    today_meal = get_todays_meal()
    data = _prepare_meal_context(today_meal, request)
    data['request'] = request
    data['user'] = context.get('user')
    return data
