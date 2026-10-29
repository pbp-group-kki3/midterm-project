from django.urls import path
from food_of_the_day import views

app_name = 'food_of_the_day'

urlpatterns = [
    path('', views.index, name='index'),
    path('slide/', views.slide_partial, name='slide_partial'),
    path('<int:meal_id>/', views.detail, name='detail'),
    path('<int:meal_id>/comment/', views.add_comment, name='add_comment'),
    path('<int:meal_id>/toggle-save/', views.toggle_save_meal, name='toggle_save_meal'),
]
