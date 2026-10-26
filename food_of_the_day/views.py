from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST

from food_of_the_day.models import MealOfTheDay, MealComment
from food_of_the_day.forms import MealCommentForm
from food_of_the_day.services import (
    get_recipe,
    extract_calories,
    get_did_you_know,
    extract_ingredients,
    extract_instructions,
)


def _prepare_meal_context(meal, request):
    """Helper to assemble all recipe and comment context for a given MealOfTheDay."""
    if not meal:
        return {'meal': None, 'recipe': None}

    recipe = get_recipe(meal.recipe_id)
    if not recipe:
        return {
            'meal': meal,
            'recipe': None,
            'error_message': 'Recipe details from Spoonacular are currently unavailable.',
        }

    calories = extract_calories(recipe)
    did_you_know = get_did_you_know(recipe)
    ingredients = extract_ingredients(recipe)
    instructions = extract_instructions(recipe)
    comments = meal.comments.select_related('user').all()

    return {
        'meal': meal,
        'recipe': recipe,
        'calories': calories,
        'did_you_know': did_you_know,
        'ingredients': ingredients,
        'instructions': instructions,
        'comments': comments,
        'comment_form': MealCommentForm(),
        'dish_types': recipe.get('dishTypes', []),
        'servings': recipe.get('servings'),
        'ready_in_minutes': recipe.get('readyInMinutes'),
        'source_name': recipe.get('sourceName') or 'Spoonacular',
        'source_url': recipe.get('sourceUrl') or 'https://spoonacular.com',
    }


def index(request):
    """
    Main page for the Meal of the Day module.
    Displays today's featured meal, detail panel (if authenticated), and comments.
    """
    today = timezone.localdate()
    today_meal = MealOfTheDay.objects.filter(date=today).first()
    context = _prepare_meal_context(today_meal, request)

    # Archive of past meals for exploration
    past_meals = MealOfTheDay.objects.filter(date__lt=today).order_by('-date')[:6]
    context['past_meals'] = past_meals
    context['is_today'] = True

    return render(request, 'food_of_the_day/index.html', context)


def detail(request, meal_id):
    """
    Detailed view for any featured meal by its database ID.
    """
    meal = get_object_or_404(MealOfTheDay, id=meal_id)
    context = _prepare_meal_context(meal, request)
    context['is_today'] = (meal.date == timezone.localdate())

    return render(request, 'food_of_the_day/detail.html', context)


def slide_partial(request):
    """
    Renders only the home page slide component.
    Used for the second slide on the home page carousel or AJAX fetch.
    """
    today = timezone.localdate()
    today_meal = MealOfTheDay.objects.filter(date=today).first()
    context = _prepare_meal_context(today_meal, request)
    return render(request, 'food_of_the_day/components/slide.html', context)


@require_POST
def add_comment(request, meal_id):
    """
    Handles comment submission on a featured meal.
    Requires user authentication.
    """
    if not request.user.is_authenticated:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Authentication required'}, status=401)
        messages.error(request, 'Please log in to leave a comment.')
        return redirect(settings.LOGIN_URL)

    meal = get_object_or_404(MealOfTheDay, id=meal_id)
    form = MealCommentForm(request.POST)

    if form.is_valid():
        comment = form.save(commit=False)
        comment.user = request.user
        comment.meal = meal
        comment.save()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'comment': {
                    'id': comment.id,
                    'user': comment.user.username,
                    'text': comment.text,
                    'created_at': comment.created_at.strftime('%b %d, %Y, %I:%M %p'),
                }
            })

        messages.success(request, 'Your comment was posted successfully!')
        return redirect(request.META.get('HTTP_REFERER') or f'/food-of-the-day/{meal.id}/')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid comment text'}, status=400)

    messages.error(request, 'Failed to post comment. Please check your text.')
    return redirect(request.META.get('HTTP_REFERER') or f'/food-of-the-day/{meal.id}/')
