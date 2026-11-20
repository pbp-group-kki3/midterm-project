"""
Views for the Meal of the Day (food_of_the_day) module.

This module provides:
1. `index`: Main page displaying today's featured meal hero, collapsible recipe drawer,
   and an archive gallery of past recommendations.
2. `detail`: Standalone recipe detail page with complete instructions, nutrition, and comments.
3. `slide_partial`: Lightweight HTML partial for the homepage carousel.
4. `add_comment`: Authenticated, anti-spam protected endpoint supporting both AJAX JSON and HTTP redirects.
5. `toggle_save_meal`: Asynchronous bookmark toggle storing immutable snapshots into the user's profile.
"""

import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.html import strip_tags
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required

from food_of_the_day.models import MealOfTheDay, MealComment, SavedMeal
from food_of_the_day.forms import MealCommentForm
from food_of_the_day.services import (
    get_recipe,
    build_recipe_snapshot,
    extract_calories,
    extract_key_nutrients,
    get_did_you_know,
    extract_ingredients,
    extract_instructions,
    is_safe_external_url,
    get_todays_meal,
)


def _get_safe_redirect_url(request, default_path):
    """
    Validates HTTP_REFERER to prevent Open Redirect attacks.
    Only allows redirects back to the exact same host and scheme.
    """
    referer = request.META.get('HTTP_REFERER')
    if referer and url_has_allowed_host_and_scheme(
        url=referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure()
    ):
        return referer
    return default_path


def _prepare_meal_context(meal, request):
    """
    Central Data Aggregator: Assembles recipe details, nutrition, comments,
    and bookmark states for a given MealOfTheDay instance.
    
    Data Flow:
    1. Look up recipe by recipe_id (cached from Spoonacular).
    2. If Spoonacular is down or rate-limited, fall back to existing DB snapshots.
    3. Sanitize external image and source URLs against XSS (no javascript: or data:).
    4. Extract structured nutritional metrics (calories, key nutrients, Did You Know?).
    5. Query user-specific bookmark status (is_saved boolean).
    """
    if not meal:
        return {'meal': None, 'recipe': None}

    # Step 1: Query Spoonacular cache / API
    recipe = get_recipe(meal.recipe_id)

    # Step 2: Graceful offline fallback using immutable saved snapshots
    if not recipe or not isinstance(recipe, dict):
        saved_snap = (
            SavedMeal.objects.filter(meal=meal).exclude(snapshot_data={}).values_list('snapshot_data', flat=True).first()
            or SavedMeal.objects.filter(recipe_id=meal.recipe_id).exclude(snapshot_data={}).values_list('snapshot_data', flat=True).first()
        )
        if saved_snap and isinstance(saved_snap, dict):
            recipe = saved_snap

    # If recipe data is completely absent from both API and DB
    if not recipe or not isinstance(recipe, dict):
        return {
            'meal': meal,
            'recipe': None,
            'error_message': 'Recipe details from Spoonacular are currently unavailable.',
        }

    # Step 3: URL sanitization to guard against javascript: or data: XSS vectors
    raw_source_url = recipe.get('sourceUrl')
    source_url = raw_source_url if is_safe_external_url(raw_source_url) else 'https://spoonacular.com'

    raw_image_url = recipe.get('image')
    safe_image_url = raw_image_url if is_safe_external_url(raw_image_url) else None

    safe_recipe = {
        **recipe,
        'image': safe_image_url,
        'sourceUrl': source_url,
    }

    # Step 4: Extract nutrition, ingredients, and instructions
    calories = extract_calories(recipe)
    key_nutrients = extract_key_nutrients(recipe)
    did_you_know = get_did_you_know(recipe)
    ingredients = extract_ingredients(recipe)
    instructions = extract_instructions(recipe)
    comments = meal.comments.select_related('user').all()

    # Step 5: Check authenticated user's bookmark state
    is_saved = False
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        is_saved = SavedMeal.objects.filter(user=request.user, meal=meal).exists()

    return {
        'meal': meal,
        'recipe': safe_recipe,
        'calories': calories,
        'key_nutrients': key_nutrients,
        'health_score': recipe.get('healthScore'),
        'did_you_know': did_you_know,
        'ingredients': ingredients,
        'instructions': instructions,
        'comments': comments,
        'comment_form': MealCommentForm(),
        'dish_types': recipe.get('dishTypes', []) if isinstance(recipe.get('dishTypes'), list) else [],
        'servings': recipe.get('servings'),
        'ready_in_minutes': recipe.get('readyInMinutes'),
        'source_name': str(recipe.get('sourceName') or 'Spoonacular')[:100],
        'source_url': source_url,
        'is_saved': is_saved,
    }


@never_cache
def index(request):
    """
    Main landing page for Meal of the Day.
    Displays:
    - Today's featured meal hero card with expandable recipe drawer.
    - Gallery of past featured meals for browsing previous recommendations.
    """
    today = timezone.localdate()
    # Auto-seed logic ensures a meal is always present, even on fresh deployments
    today_meal = get_todays_meal()
    context = _prepare_meal_context(today_meal, request)

    # Archive of past meals (ordered newest to oldest)
    past_meals = MealOfTheDay.objects.filter(date__lt=today).order_by('-date')[:6]
    context['past_meals'] = past_meals
    context['is_today'] = True

    return render(request, 'food_of_the_day/index.html', context)


@never_cache
def detail(request, meal_id):
    """
    Dedicated detail view for any featured meal by its database ID.
    Renders full steps, ingredients, nutrition facts, and community discussion.
    """
    meal = get_object_or_404(MealOfTheDay, id=meal_id)
    context = _prepare_meal_context(meal, request)
    context['is_today'] = (meal.date == timezone.localdate())
    context['is_detail'] = True  # Informs slide.html not to render duplicate panels

    return render(request, 'food_of_the_day/detail.html', context)


@never_cache
def slide_partial(request):
    """
    Renders only the home page hero slide component.
    Embedded in the main homepage carousel via templatetag or fetched via AJAX.
    """
    today_meal = get_todays_meal()
    context = _prepare_meal_context(today_meal, request)
    return render(request, 'food_of_the_day/components/slide.html', context)


@require_POST
def add_comment(request, meal_id):
    """
    Handles comment submission on a featured meal.
    Features:
    - Requires authentication (redirects or returns 401 JSON for AJAX).
    - Enforces anti-spam flood protection (10-second cooldown per duplicate comment).
    - Returns JSON payload when called asynchronously via AJAX, or redirects safely.
    """
    if not request.user.is_authenticated:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Authentication required'}, status=401)
        messages.error(request, 'Please log in to leave a comment.')
        return redirect(settings.LOGIN_URL)

    meal = get_object_or_404(MealOfTheDay, id=meal_id)
    form = MealCommentForm(request.POST)
    fallback_url = f'/food-of-the-day/{meal.id}/'

    if form.is_valid():
        cleaned_text = form.cleaned_data['text']

        # Anti-spam protection: prevent identical comments posted within 10 seconds
        ten_seconds_ago = timezone.now() - datetime.timedelta(seconds=10)
        is_duplicate = MealComment.objects.filter(
            user=request.user,
            meal=meal,
            text=cleaned_text,
            created_at__gte=ten_seconds_ago
        ).exists()

        if is_duplicate:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Duplicate comment submitted too quickly. Please wait a moment.'}, status=429)
            messages.warning(request, 'You recently posted this comment. Please wait a moment before posting again.')
            return redirect(_get_safe_redirect_url(request, fallback_url))

        # Save valid comment
        comment = form.save(commit=False)
        comment.user = request.user
        comment.meal = meal
        comment.save()

        # Respond asynchronously for smooth AJAX DOM update
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
        return redirect(_get_safe_redirect_url(request, fallback_url))

    # Form validation errors
    first_error = form.errors.get('text', ['Invalid comment.'])[0]
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'error': str(first_error)}, status=400)

    messages.error(request, f'Failed to post comment: {first_error}')
    return redirect(_get_safe_redirect_url(request, fallback_url))


@login_required(login_url='login')
@require_POST
def toggle_save_meal(request, meal_id):
    """
    Toggle saving/bookmarking a Meal of the Day for the current user.
    
    Snapshot Integration:
    - If already saved: deletes bookmark and unsaves.
    - If unsaved: captures point-in-time recipe snapshot (calories, ingredients, steps)
      and stores it in SavedMeal.snapshot_data.
    - Returns JSON for AJAX optimistic UI toggling or redirects safely.
    """
    meal = get_object_or_404(MealOfTheDay, id=meal_id)
    saved_record = SavedMeal.objects.filter(user=request.user, meal=meal).first()
    # notes = request.POST.get('notes', '').strip()
    # SavedMeal.objects.create(..., notes=notes)

    if saved_record:
        # Unsave action
        saved_record.delete()
        saved = False
        msg = "Meal removed from your Saved collection."
    else:
        # Save action: generate snapshot
        recipe = get_recipe(meal.recipe_id)
        snapshot = build_recipe_snapshot(recipe)

        # Derive trusted server-side title
        canonical_title = snapshot.get('title') or (str(recipe.get('title') or '') if isinstance(recipe, dict) else '')
        if canonical_title:
            recipe_title = canonical_title[:255]
        else:
            raw_title = request.POST.get('recipe_title', '')
            recipe_title = strip_tags(raw_title).strip()[:255]

        SavedMeal.objects.create(
            user=request.user,
            meal=meal,
            recipe_id=meal.recipe_id,
            recipe_title=recipe_title,
            snapshot_data=snapshot,
        )
        saved = True
        msg = "Meal saved to your profile!"

    # Asynchronous AJAX response
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({
            'saved': saved,
            'meal_id': meal.id,
            'message': msg,
        })

    # Standard form submit fallback
    messages.success(request, msg)
    next_url = request.POST.get('next', '')
    if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(next_url)
    return redirect('food_of_the_day:detail', meal_id=meal.id)

#@login_required
#@require_POST
#def delete_comment(request, comment_id):
    comment = get_object_or_404(MealComment, id=comment_id, user=request.user)  # Security: user=request.user prevents IDOR
    comment.delete()
    return redirect('food_of_the_day:detail', meal_id=comment.meal_id)