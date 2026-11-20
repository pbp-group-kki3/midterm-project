from django.urls import path
from food_of_the_day import api_views

urlpatterns = [
    path('', api_views.meal_of_the_day_list, name='api_meal_list'),
    path('saved/', api_views.saved_meals_list, name='api_saved_meals'),
    path('<int:meal_id>/', api_views.meal_of_the_day_detail, name='api_meal_detail'),
    path('<int:meal_id>/comments/', api_views.meal_comments, name='api_meal_comments'),
    path('comments/<int:comment_id>/', api_views.delete_meal_comment, name='api_delete_comment'),
    path('<int:meal_id>/save/', api_views.toggle_save_meal_api, name='api_toggle_save_meal'),
]