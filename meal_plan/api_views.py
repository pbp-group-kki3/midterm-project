from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from meal_plan.constants import (
    ALLERGY_CHOICES,
    DEFAULT_CALORIES,
    DEFAULT_DAYS,
    DIET_CHIP_CHOICES,
    MAX_CALORIES,
    MAX_DAYS,
    MAX_RECIPE_PAGES,
    MEAL_FILTER_CHOICES,
    MIN_CALORIES,
    MIN_DAYS,
    RECIPES_PER_PAGE,
)
from meal_plan.forms import RecipeFilterForm
from meal_plan.models import MealPlan, MealPlanEntry
from meal_plan.serializers import (
    MealPlanInputSerializer,
    MealPlanSerializer,
    PlanDaySerializer,
    RecipeSerializer,
    ReplacementSerializer,
)
from meal_plan.services import planner
from meal_plan.services.spoonacular import SpoonacularError
from meal_plan.views import MAX_SWAP_ROUNDS, OFFERS_KEY, _bounded_int, _remember_offers

SNACK_WARNING = "We couldn't add snacks right now, so this plan has no snacks."
OFFER_GONE = 'That recipe is no longer on offer. Please pick again.'
LIST_FIELDS = ('diet', 'allergies')


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


def failure_response(error):
    if isinstance(error, planner.PlanError):
        return Response({'detail': error.message}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'detail': error.message}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


def own_plan(request, pk):
    return get_object_or_404(MealPlan, pk=pk, user=request.user)


def own_meal(request, pk, entry_pk):
    plan = own_plan(request, pk)
    return plan, get_object_or_404(MealPlanEntry, pk=entry_pk, plan=plan)


def snack_warning(data, plan):
    return SNACK_WARNING if data['include_snack'] and not plan.include_snack else None


def current_values(plan):
    return {
        'name': plan.name,
        'start_date': plan.date,
        'days': plan.days,
        'diet': plan.diet_keys,
        'allergies': plan.allergies,
        'include_snack': plan.include_snack,
        'calorie_goal': plan.calorie_goal,
    }


def merged_values(plan, data):
    values = current_values(plan)
    for key in values:
        if key not in data:
            continue
        if key in LIST_FIELDS and hasattr(data, 'getlist'):
            values[key] = data.getlist(key)
        else:
            values[key] = data[key]
    return values


class MealPlanListAPI(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = request.user.meal_plans.annotate(meal_count=Count('entries'))
        return Response(MealPlanSerializer(plans, many=True).data)

    def post(self, request):
        serializer = MealPlanInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            plan = planner.create_plan(request.user, serializer.validated_data)
        except (planner.PlanError, SpoonacularError) as error:
            return failure_response(error)
        data = MealPlanSerializer(plan).data
        data['warning'] = snack_warning(serializer.validated_data, plan)
        return Response(data, status=status.HTTP_201_CREATED)


class MealPlanDetailAPI(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        plan = own_plan(request, pk)
        days, error = planner.plan_days(plan)
        data = MealPlanSerializer(plan).data
        data['schedule'] = PlanDaySerializer(days, many=True).data
        data['error'] = error.message if error else None
        return Response(data)

    def put(self, request, pk):
        return self.save_changes(own_plan(request, pk), request.data)

    def patch(self, request, pk):
        plan = own_plan(request, pk)
        return self.save_changes(plan, merged_values(plan, request.data))

    def delete(self, request, pk):
        own_plan(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def save_changes(self, plan, values):
        serializer = MealPlanInputSerializer(data=values)
        serializer.is_valid(raise_exception=True)
        try:
            new_meals = planner.update_plan(plan, serializer.validated_data)
        except (planner.PlanError, SpoonacularError) as error:
            return failure_response(error)
        data = MealPlanSerializer(plan).data
        data['new_meals'] = new_meals
        data['warning'] = snack_warning(serializer.validated_data, plan) if new_meals else None
        return Response(data)


class MealOptionsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, entry_pk):
        plan, entry = own_meal(request, pk, entry_pk)
        round_number = _bounded_int(request.query_params.get('round'), 0, 0, MAX_SWAP_ROUNDS)
        try:
            current, options = planner.replacement_options(plan, entry, round_number)
        except SpoonacularError as error:
            return failure_response(error)
        _remember_offers(request, entry, options)
        return Response({
            'current': RecipeSerializer(current).data if current else None,
            'options': ReplacementSerializer(options, many=True).data,
            'next_round': min(round_number + 1, MAX_SWAP_ROUNDS),
        })


class MealReplaceAPI(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, entry_pk):
        plan, entry = own_meal(request, pk, entry_pk)
        offers = request.session.get(OFFERS_KEY, {})
        recipe_id = _bounded_int(request.data.get('recipe_id'), None, 1, 10 ** 9)
        if recipe_id is None or recipe_id not in offers.get(str(entry.pk), []):
            return Response({'detail': OFFER_GONE}, status=status.HTTP_400_BAD_REQUEST)
        entry.recipe_id = recipe_id
        entry.save(update_fields=['recipe_id'])
        offers = dict(offers)
        offers.pop(str(entry.pk), None)
        request.session[OFFERS_KEY] = offers
        cards, _ = planner.recipe_cards([recipe_id])
        return Response({
            'id': entry.pk,
            'day': entry.day,
            'slot': entry.slot,
            'slot_label': entry.get_slot_display(),
            'recipe': RecipeSerializer(cards[recipe_id]).data,
        })


class RecipeSearchAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params.copy()
        params.pop('page', None)
        page = _bounded_int(request.query_params.get('page'), 1, 1, MAX_RECIPE_PAGES)
        form = RecipeFilterForm(params)
        if not form.is_valid():
            errors = {field: [item['message'] for item in items] for field, items in form.errors.get_json_data().items()}
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            cards, total = planner.browse_recipes(form.cleaned_data, page)
        except SpoonacularError as error:
            return failure_response(error)
        shown = (page - 1) * RECIPES_PER_PAGE + len(cards)
        more = len(cards) == RECIPES_PER_PAGE and total > shown and page < MAX_RECIPE_PAGES
        return Response({
            'results': RecipeSerializer(cards, many=True).data,
            'page': page,
            'total': total,
            'next_page': page + 1 if more else None,
        })


class PlanFormOptionsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        defaults = planner.profile_defaults(request.user)
        return Response({
            'diets': [{'key': key, 'label': label} for key, label in DIET_CHIP_CHOICES],
            'allergies': [{'key': key, 'label': label} for key, label in ALLERGY_CHOICES],
            'meal_types': [{'key': key, 'label': label} for key, label in MEAL_FILTER_CHOICES],
            'days': {'min': MIN_DAYS, 'max': MAX_DAYS, 'default': DEFAULT_DAYS},
            'calorie_goal': {
                'min': MIN_CALORIES,
                'max': MAX_CALORIES,
                'default': defaults['calorie_target'] or DEFAULT_CALORIES,
            },
            'defaults': {
                'start_date': timezone.localdate(),
                'diet': defaults['diets'],
                'allergies': defaults['allergies'],
                'include_snack': defaults['include_snack'],
            },
        })
