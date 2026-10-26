from django import template
from django.utils import timezone
from food_of_the_day.models import MealOfTheDay
from food_of_the_day.views import _prepare_meal_context

register = template.Library()


@register.inclusion_tag('food_of_the_day/components/slide.html', takes_context=True)
def meal_of_the_day_slide(context):
    """
    Renders the second slide on the home page for Meal of the Day.
    If no entry exists for today, meal is None and the component can be cleanly skipped.
    """
    request = context.get('request')
    today = timezone.localdate()
    today_meal = MealOfTheDay.objects.filter(date=today).first()
    data = _prepare_meal_context(today_meal, request)
    data['request'] = request
    data['user'] = context.get('user')
    data['show_carousel_dots'] = True
    return data
