import datetime
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from food_of_the_day.models import MealOfTheDay, MealComment, SavedMeal
from food_of_the_day.serializers import (
    MealCommentSerializer,
    MealOfTheDaySerializer,
    SavedMealSerializer,
)
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


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Allows session-authenticated mobile clients (e.g. Flutter CookieRequest) to POST/DELETE."""
    def enforce_csrf(self, request):
        return


def _resolve_recipe(meal):
    """Fetch recipe from Spoonacular cache or fall back to an existing DB snapshot."""
    recipe = get_recipe(meal.recipe_id)
    if not recipe or not isinstance(recipe, dict):
        saved_snap = (
            SavedMeal.objects.filter(meal=meal)
            .exclude(snapshot_data={})
            .values_list('snapshot_data', flat=True)
            .first()
            or SavedMeal.objects.filter(recipe_id=meal.recipe_id)
            .exclude(snapshot_data={})
            .values_list('snapshot_data', flat=True)
            .first()
        )
        if saved_snap and isinstance(saved_snap, dict):
            recipe = saved_snap
    return recipe if isinstance(recipe, dict) else None


def _build_meal_payload(meal, request, include_comments=True):
    recipe = _resolve_recipe(meal)
    is_saved = (
        request.user.is_authenticated
        and SavedMeal.objects.filter(user=request.user, meal=meal).exists()
    )

    payload = {
        'id': meal.id,
        'date': meal.date.isoformat(),
        'recipe_id': meal.recipe_id,
        'is_today': meal.date == timezone.localdate(),
        'is_saved': is_saved,
        'recipe': None,
    }

    if recipe:
        raw_source_url = recipe.get('sourceUrl') or recipe.get('source_url')
        source_url = raw_source_url if is_safe_external_url(raw_source_url) else 'https://spoonacular.com'
        raw_image_url = recipe.get('image')
        safe_image_url = raw_image_url if is_safe_external_url(raw_image_url) else None

        payload['recipe'] = {
            'id': recipe.get('id', meal.recipe_id),
            'title': str(recipe.get('title') or '').strip(),
            'image': safe_image_url,
            'calories': extract_calories(recipe) if 'nutrition' in recipe else recipe.get('calories'),
            'key_nutrients': extract_key_nutrients(recipe) if 'nutrition' in recipe else recipe.get('key_nutrients', []),
            'health_score': recipe.get('healthScore', recipe.get('health_score')),
            'did_you_know': get_did_you_know(recipe) if 'nutrition' in recipe else recipe.get('did_you_know', []),
            'ingredients': extract_ingredients(recipe) if 'extendedIngredients' in recipe else recipe.get('ingredients', []),
            'instructions': extract_instructions(recipe) if 'analyzedInstructions' in recipe else recipe.get('instructions', []),
            'dish_types': recipe.get('dishTypes', recipe.get('dish_types', [])),
            'servings': recipe.get('servings'),
            'ready_in_minutes': recipe.get('readyInMinutes', recipe.get('ready_in_minutes')),
            'source_name': str(recipe.get('sourceName') or recipe.get('source_name') or 'Spoonacular')[:100],
            'source_url': source_url,
        }
    else:
        payload['error_message'] = 'Recipe details from Spoonacular are currently unavailable.'

    if include_comments:
        comments = meal.comments.select_related('user').all()
        payload['comments'] = MealCommentSerializer(
            comments, many=True, context={'request': request}
        ).data

    return payload


@api_view(['GET'])
@permission_classes([AllowAny])
def meal_of_the_day_list(request):
    """GET /api/food-of-the-day/ — Returns today's featured meal and the 6 most recent past meals."""
    today = timezone.localdate()
    today_meal = get_todays_meal()
    past_meals = MealOfTheDay.objects.filter(date__lt=today).order_by('-date')[:6]

    return Response({
        'today': _build_meal_payload(today_meal, request, include_comments=True),
        'past_meals': MealOfTheDaySerializer(past_meals, many=True).data,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def meal_of_the_day_detail(request, meal_id):
    """GET /api/food-of-the-day/<meal_id>/ — Returns full recipe details, nutrition, comments, and save state."""
    meal = get_object_or_404(MealOfTheDay, id=meal_id)
    return Response(_build_meal_payload(meal, request, include_comments=True))


@api_view(['GET', 'POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
def meal_comments(request, meal_id):
    """
    GET  /api/food-of-the-day/<meal_id>/comments/ — List comments for a meal.
    POST /api/food-of-the-day/<meal_id>/comments/ — Create a comment (auth required, 10s anti-spam).
    """
    meal = get_object_or_404(MealOfTheDay, id=meal_id)

    if request.method == 'GET':
        comments = meal.comments.select_related('user').all()
        serializer = MealCommentSerializer(comments, many=True, context={'request': request})
        return Response(serializer.data)

    if not request.user.is_authenticated:
        return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = MealCommentSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    cleaned_text = serializer.validated_data['text']
    ten_seconds_ago = timezone.now() - datetime.timedelta(seconds=10)
    is_duplicate = MealComment.objects.filter(
        user=request.user,
        meal=meal,
        text=cleaned_text,
        created_at__gte=ten_seconds_ago,
    ).exists()

    if is_duplicate:
        return Response(
            {'error': 'Duplicate comment submitted too quickly. Please wait a moment.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    comment = serializer.save(user=request.user, meal=meal)
    return Response(
        MealCommentSerializer(comment, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['DELETE'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def delete_meal_comment(request, comment_id):
    """DELETE /api/food-of-the-day/comments/<comment_id>/ — Delete the authenticated user's own comment."""
    comment = get_object_or_404(MealComment, id=comment_id, user=request.user)
    comment.delete()
    return Response({'deleted': True, 'comment_id': comment_id}, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def toggle_save_meal_api(request, meal_id):
    """POST /api/food-of-the-day/<meal_id>/save/ — Toggle bookmark with immutable recipe snapshot."""
    meal = get_object_or_404(MealOfTheDay, id=meal_id)
    saved_record = SavedMeal.objects.filter(user=request.user, meal=meal).first()

    if saved_record:
        saved_record.delete()
        return Response({
            'saved': False,
            'meal_id': meal.id,
            'message': 'Meal removed from your Saved collection.',
        })

    recipe = get_recipe(meal.recipe_id)
    snapshot = build_recipe_snapshot(recipe)

    canonical_title = snapshot.get('title') or (
        str(recipe.get('title') or '') if isinstance(recipe, dict) else ''
    )
    if canonical_title:
        recipe_title = canonical_title[:255]
    else:
        raw_title = request.data.get('recipe_title', '')
        recipe_title = strip_tags(str(raw_title)).strip()[:255]

    SavedMeal.objects.create(
        user=request.user,
        meal=meal,
        recipe_id=meal.recipe_id,
        recipe_title=recipe_title,
        snapshot_data=snapshot,
    )
    return Response(
        {
            'saved': True,
            'meal_id': meal.id,
            'message': 'Meal saved to your profile!',
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def saved_meals_list(request):
    """GET /api/food-of-the-day/saved/ — List the authenticated user's saved meals and snapshots."""
    saved_meals = SavedMeal.objects.filter(user=request.user).select_related('meal')
    serializer = SavedMealSerializer(saved_meals, many=True)
    return Response(serializer.data)