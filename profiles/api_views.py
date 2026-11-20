from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse

from blog.models import SavedArticle
from comparison.models import SavedComparison
from main.models import FavoriteProduct
from profiles.preferences import ALLERGY_CHOICES, DIET_CHOICES
from profiles.saved import SAVED_CATEGORIES, saved_items
from profiles.serializers import ProfileSerializer, RegisterSerializer


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


@api_view(["GET"])
@permission_classes([AllowAny])
def api_auth_root(request):
    return Response(
        {
            "login": reverse("api_login", request=request),
            "register": reverse("api_register", request=request),
            "logout": reverse("api_logout", request=request),
            "profile": reverse("api_profile", request=request),
            "saved": reverse("api_saved_list", request=request),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET", "POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def api_login(request):
    if request.method == "GET":
        return Response(
            {
                "authenticated": request.user.is_authenticated,
                "username": request.user.username if request.user.is_authenticated else None,
                "post_payload_example": {
                    "username": "your_username",
                    "password": "your_password",
                },
            },
            status=status.HTTP_200_OK,
        )

    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {
                "status": False,
                "message": "Invalid username or password.",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return Response(
            {
                "status": False,
                "message": "Account is disabled.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    login(request, user)
    return Response(
        {
            "status": True,
            "message": "Login successful!",
            "username": user.username,
            "email": user.email,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET", "POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def api_register(request):
    if request.method == "GET":
        return Response(
            {
                "available_diets": [k for k, _ in DIET_CHOICES],
                "available_allergies": [k for k, _ in ALLERGY_CHOICES],
                "post_payload_example": {
                    "username": "newuser",
                    "email": "newuser@example.com",
                    "password": "strongpassword123",
                    "password2": "strongpassword123",
                    "diet": ["halal"],
                    "allergies": ["Peanuts"],
                },
            },
            status=status.HTTP_200_OK,
        )

    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "status": False,
                "message": "Registration failed.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = serializer.save()
    return Response(
        {
            "status": True,
            "message": "Account created successfully!",
            "username": user.username,
            "email": user.email,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def api_logout(request):
    if request.method == "GET":
        return Response(
            {
                "authenticated": request.user.is_authenticated,
                "username": request.user.username if request.user.is_authenticated else None,
                "detail": "Click POST below to log out.",
            },
            status=status.HTTP_200_OK,
        )

    username = request.user.username if request.user.is_authenticated else ""
    logout(request)
    return Response(
        {
            "status": True,
            "message": "Logged out successfully!",
            "username": username,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET", "PUT", "PATCH"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def api_profile(request):
    profile = request.user.profile

    if request.method == "GET":
        serializer = ProfileSerializer(profile, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    serializer = ProfileSerializer(
        profile,
        data=request.data,
        partial=True,
        context={"request": request},
    )
    if serializer.is_valid():
        serializer.save()
        return Response(
            {
                "status": True,
                "message": "Profile updated successfully.",
                "profile": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    return Response(
        {
            "status": False,
            "message": "Invalid profile data.",
            "errors": serializer.errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_saved_list(request):
    valid_categories = {key for key, _ in SAVED_CATEGORIES}
    category = request.query_params.get("category", "all").lower()
    if category not in valid_categories:
        category = "all"

    raw_items = saved_items(request.user, category)
    serialized = [
        {
            "title": item["title"],
            "type": item["type"],
            "metadata": item["metadata"],
            "created_at": item["created_at"].isoformat()
            if item.get("created_at")
            else None,
            "open_url": item.get("open_url"),
            "remove_url": item.get("remove_url"),
        }
        for item in raw_items
    ]

    return Response(
        {
            "category": category,
            "count": len(serialized),
            "items": serialized,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST", "DELETE"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def api_saved_remove(request, item_type, pk):
    item_type = item_type.lower()

    if item_type == "product":
        obj = get_object_or_404(FavoriteProduct, pk=pk, user=request.user)
    elif item_type == "comparison":
        obj = get_object_or_404(SavedComparison, pk=pk, user=request.user)
    elif item_type == "article":
        obj = get_object_or_404(SavedArticle, pk=pk, user=request.user)
    elif item_type == "meal":
        from food_of_the_day.models import SavedMeal

        obj = get_object_or_404(SavedMeal, pk=pk, user=request.user)
    else:
        return Response(
            {"status": False, "message": f"Unknown saved item type: {item_type}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    obj.delete()
    return Response(
        {"status": True, "message": "Saved item removed."},
        status=status.HTTP_200_OK,
    )