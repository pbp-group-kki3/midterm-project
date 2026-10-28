from django.urls import path, include

urlpatterns = [
    path('food-of-the-day/', include('food_of_the_day.urls')),
]
