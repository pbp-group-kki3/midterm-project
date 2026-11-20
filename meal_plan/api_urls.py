from django.urls import path

from meal_plan import api_views

app_name = 'meal_plan_api'

urlpatterns = [
    path('', api_views.MealPlanListAPI.as_view(), name='plans'),
    path('form-options/', api_views.PlanFormOptionsAPI.as_view(), name='form_options'),
    path('recipes/', api_views.RecipeSearchAPI.as_view(), name='recipes'),
    path('<int:pk>/', api_views.MealPlanDetailAPI.as_view(), name='plan'),
    path('<int:pk>/meals/<int:entry_pk>/options/', api_views.MealOptionsAPI.as_view(), name='meal_options'),
    path('<int:pk>/meals/<int:entry_pk>/replace/', api_views.MealReplaceAPI.as_view(), name='meal_replace'),
]
