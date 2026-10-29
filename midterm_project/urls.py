"""
URL configuration for midterm_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from midterm_project.placeholders import coming_soon, modules
from midterm_project.styleguide import styleguide
from django.contrib.auth.views import LogoutView
from profiles.views import (
    ProfileLoginView,
    change_password_view,
    profile_delete,
    profile_edit,
    profile_picture_delete,
    profile_saved,
    profile_saved_comparison,
    profile_saved_remove,
    profile_view,
    register_view,
)
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),

    path('modules/', modules),

    path('styleguide/', styleguide),

    path('meal-plan/', include('meal_plan.urls')),

    path("compare/", include("comparison.urls")),
    
    path("food-of-the-day/", include("food_of_the_day.urls")),

    path('blog/', include('blog.urls')),

    path('profiles/register/', register_view, name='register'),
    path("profiles/login/", ProfileLoginView.as_view(), name="login"),
    path('profiles/logout/', LogoutView.as_view(next_page='login'), name='logout'),

    path('profiles/', profile_view, name='profile'),
    path('profiles/edit/', profile_edit, name='profile_edit'),
    path('profiles/delete/', profile_delete, name='profile_delete'),
    path('profiles/picture/delete/', profile_picture_delete, name='profile_picture_delete'),
    path('password/', change_password_view, name='change_password'),
    path("profiles/saved/", profile_saved, name="profile_saved"),
    path("profiles/saved/comparisons/<int:pk>/", profile_saved_comparison, name="profile_saved_comparison"),
    path("profiles/saved/<str:kind>/<int:pk>/remove/", profile_saved_remove, name="profile_saved_remove"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)