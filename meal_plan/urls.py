from django.urls import path
from django.views.generic import RedirectView

from meal_plan import views

app_name = 'meal_plan'

urlpatterns = [
    path('', views.recipes, name='recipes'),
    path('recipes/', RedirectView.as_view(pattern_name='meal_plan:recipes', query_string=True)),
    path('plans/', views.plan_list, name='plan_list'),
    path('plans/new/', views.plan_create, name='plan_create'),
    path('plans/<int:pk>/', views.plan_detail, name='plan_detail'),
    path('plans/<int:pk>/delete/', views.plan_delete, name='plan_delete'),
    path('plans/<int:pk>/meals/<int:entry_pk>/replace/', views.meal_replace, name='meal_replace'),
]
