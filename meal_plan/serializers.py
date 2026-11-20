from rest_framework import serializers

from meal_plan.constants import (
    ALLERGY_CHOICES,
    DIET_CHIP_CHOICES,
    MAX_CALORIES,
    MAX_DAYS,
    MIN_CALORIES,
    MIN_DAYS,
    PLANT_BASED_DIETS,
)
from meal_plan.models import MealPlan

NAME_MESSAGE = 'Give your plan a name.'
DAYS_MESSAGE = f'Enter a number between {MIN_DAYS} and {MAX_DAYS}.'
CALORIES_MESSAGE = f'Enter a goal between {MIN_CALORIES:,} and {MAX_CALORIES:,} kcal.'
DIET_CONFLICT_MESSAGE = "Ketogenic can't be combined with vegetarian, vegan or pescatarian in one plan."


def in_choice_order(choices, chosen):
    return [key for key, _ in choices if key in chosen]


class MealPlanSerializer(serializers.ModelSerializer):
    start_date = serializers.DateField(source='date', read_only=True)
    end_date = serializers.DateField(read_only=True)
    diets = serializers.ListField(source='diet_keys', child=serializers.CharField(), read_only=True)
    diet_labels = serializers.ListField(child=serializers.CharField(), read_only=True)
    allergy_labels = serializers.ListField(source='allergy_badges', child=serializers.CharField(), read_only=True)
    meal_count = serializers.SerializerMethodField()

    class Meta:
        model = MealPlan
        fields = [
            'id',
            'name',
            'start_date',
            'end_date',
            'days',
            'diets',
            'diet_labels',
            'allergies',
            'allergy_labels',
            'include_snack',
            'calorie_goal',
            'meal_count',
            'created_at',
        ]
        read_only_fields = fields

    def get_meal_count(self, plan):
        count = getattr(plan, 'meal_count', None)
        return plan.entries.count() if count is None else count


class RecipeSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    image_url = serializers.CharField(read_only=True)
    ready_in_minutes = serializers.IntegerField(read_only=True, allow_null=True)
    servings = serializers.IntegerField(read_only=True, allow_null=True)
    calories = serializers.IntegerField(read_only=True, allow_null=True)
    protein = serializers.FloatField(read_only=True, allow_null=True)
    carbs = serializers.FloatField(read_only=True, allow_null=True)
    fat = serializers.FloatField(read_only=True, allow_null=True)
    source_name = serializers.CharField(read_only=True)
    source_url = serializers.CharField(read_only=True)
    labels = serializers.ListField(child=serializers.CharField(), read_only=True)
    available = serializers.BooleanField(read_only=True)


class ReplacementSerializer(RecipeSerializer):
    in_plan = serializers.BooleanField(read_only=True)


class MealSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='entry.pk', read_only=True)
    slot = serializers.CharField(source='entry.slot', read_only=True)
    slot_label = serializers.CharField(source='entry.get_slot_display', read_only=True)
    recipe = RecipeSerializer(read_only=True)


class PlanDaySerializer(serializers.Serializer):
    day = serializers.IntegerField(source='number', read_only=True)
    date = serializers.DateField(read_only=True)
    calories = serializers.IntegerField(read_only=True, allow_null=True)
    meals = MealSerializer(many=True, read_only=True)


class MealPlanInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60, error_messages={'required': NAME_MESSAGE, 'blank': NAME_MESSAGE})
    start_date = serializers.DateField(error_messages={'required': 'Pick a start date.', 'invalid': 'Enter a valid date.'})
    days = serializers.IntegerField(
        min_value=MIN_DAYS,
        max_value=MAX_DAYS,
        error_messages={key: DAYS_MESSAGE for key in ('required', 'invalid', 'min_value', 'max_value')},
    )
    diet = serializers.MultipleChoiceField(choices=DIET_CHIP_CHOICES, required=False, default=list)
    allergies = serializers.MultipleChoiceField(choices=ALLERGY_CHOICES, required=False, default=list)
    include_snack = serializers.BooleanField(required=False, default=False)
    calorie_goal = serializers.IntegerField(
        min_value=MIN_CALORIES,
        max_value=MAX_CALORIES,
        required=False,
        allow_null=True,
        default=None,
        error_messages={key: CALORIES_MESSAGE for key in ('invalid', 'min_value', 'max_value')},
    )

    def validate_name(self, value):
        return ' '.join(value.split())

    def validate_diet(self, value):
        diets = in_choice_order(DIET_CHIP_CHOICES, value)
        if 'ketogenic' in diets and any(key in diets for key in PLANT_BASED_DIETS):
            raise serializers.ValidationError(DIET_CONFLICT_MESSAGE)
        return diets

    def validate_allergies(self, value):
        return in_choice_order(ALLERGY_CHOICES, value)
