from django.urls import include, path

from midterm_project.urls import urlpatterns as project_urlpatterns

urlpatterns = [
    path('meal-plan/', include('meal_plan.urls')),
] + [pattern for pattern in project_urlpatterns if str(pattern.pattern) != 'meal-plan/']
