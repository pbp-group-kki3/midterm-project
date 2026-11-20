"""
URL routing configuration for the Meal of the Day module.

Endpoints:
- /food-of-the-day/                 -> Main landing page (hero, recipe drawer, archive gallery)
- /food-of-the-day/slide/           -> Partial HTML for homepage carousel integration
- /food-of-the-day/<id>/            -> Dedicated single-meal detail page
- /food-of-the-day/<id>/comment/    -> POST endpoint for posting community comments (AJAX + redirect)
- /food-of-the-day/<id>/toggle-save/-> POST endpoint for saving/unsaving meals with snapshot data
"""

from django.urls import path
from food_of_the_day import views

app_name = 'food_of_the_day'

urlpatterns = [
    # Main catalog & landing page
    path('', views.index, name='index'),

    # Lightweight slide partial for homepage carousel embedding
    path('slide/', views.slide_partial, name='slide_partial'),

    # Full recipe detail page for a specific featured meal
    path('<int:meal_id>/', views.detail, name='detail'),

    # Comment submission endpoint (supports both standard form POST and asynchronous AJAX)
    path('<int:meal_id>/comment/', views.add_comment, name='add_comment'),

    # Bookmark toggle endpoint with snapshot generation (AJAX & redirect)
    path('<int:meal_id>/toggle-save/', views.toggle_save_meal, name='toggle_save_meal'),
]
