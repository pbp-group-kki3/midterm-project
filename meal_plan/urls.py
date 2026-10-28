from django.urls import path

from meal_plan import views

app_name = 'meal_plan'

urlpatterns = [
    path('', views.plan_list, name='plan_list'),
    path('plans/new/', views.plan_create, name='plan_create'),
    path('plans/<int:pk>/', views.plan_detail, name='plan_detail'),
    path('plans/<int:pk>/delete/', views.plan_delete, name='plan_delete'),
    path('plans/<int:pk>/meals/<int:entry_pk>/replace/', views.meal_replace, name='meal_replace'),
    path('recipes/', views.recipes, name='recipes'),
]
