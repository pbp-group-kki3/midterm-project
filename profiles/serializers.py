from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from profiles.forms import parse_birth_date
from profiles.models import Profile
from profiles.preferences import (
    ALLERGY_CHOICES,
    DIET_CHOICES,
    normalize_allergies,
    normalize_diets,
)
from profiles.services import get_preferences


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)
    diet = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    allergies = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value.strip()).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value.strip()

    def validate_email(self, value):
        email = value.strip()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("This email is already registered.")
        return email

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        attrs["diet"] = normalize_diets(attrs.get("diet", []))
        attrs["allergies"] = normalize_allergies(attrs.get("allergies", []))
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        profile = user.profile
        profile.diet = validated_data["diet"]
        profile.allergies = validated_data["allergies"]
        profile.save()
        return user


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    computed_preferences = serializers.SerializerMethodField()
    available_diets = serializers.SerializerMethodField()
    available_allergies = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "username",
            "email",
            "full_name",
            "date_of_birth",
            "domicile",
            "profile_picture",
            "diet",
            "allergies",
            "calorie_target",
            "meals_per_day",
            "computed_preferences",
            "available_diets",
            "available_allergies",
        ]

    def get_computed_preferences(self, obj):
        return get_preferences(obj.user)

    def get_available_diets(self, obj):
        return [{"value": k, "label": v} for k, v in DIET_CHOICES]

    def get_available_allergies(self, obj):
        return [{"value": k, "label": v} for k, v in ALLERGY_CHOICES]

    def validate_date_of_birth(self, value):
        if not value:
            return ""
        parsed = parse_birth_date(value)
        if not parsed:
            raise serializers.ValidationError("Use YYYY-MM-DD or DD/MM/YYYY format.")
        if parsed > timezone.localdate():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        return parsed.isoformat()

    def validate_diet(self, value):
        return normalize_diets(value)

    def validate_allergies(self, value):
        return normalize_allergies(value)

    def validate_calorie_target(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Calorie target must be at least 1.")
        return value