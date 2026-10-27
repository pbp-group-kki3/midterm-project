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
from midterm_project.placeholders import coming_soon, modules
from midterm_project.styleguide import styleguide

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),

    path('modules/', modules),

    path('styleguide/', styleguide),

    path('meal-plan/', coming_soon, {'slug': 'meal-plan'}),

    path('compare/', coming_soon, {'slug': 'compare'}),

    path('food-of-the-day/', include('food_of_the_day.urls')),

    path('blog/', coming_soon, {'slug': 'blog'}),

    re_path(r'^profiles/', coming_soon, {'slug': 'profiles'}),
]
