from rest_framework import serializers
from food_of_the_day.models import MealOfTheDay, MealComment, SavedMeal


class MealCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = MealComment
        fields = ['id', 'username', 'text', 'created_at', 'is_owner']
        read_only_fields = ['id', 'username', 'created_at', 'is_owner']

    def get_is_owner(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.user_id == request.user.id)

    def validate_text(self, value):
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Comment must be at least 2 characters long.")
        if len(cleaned) > 1000:
            raise serializers.ValidationError("Comment cannot exceed 1000 characters.")
        return cleaned


class MealOfTheDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = MealOfTheDay
        fields = ['id', 'date', 'recipe_id', 'created_at']


class SavedMealSerializer(serializers.ModelSerializer):
    meal_id = serializers.IntegerField(source='meal.id', read_only=True, allow_null=True)

    class Meta:
        model = SavedMeal
        fields = ['id', 'meal_id', 'recipe_id', 'recipe_title', 'snapshot_data', 'created_at']