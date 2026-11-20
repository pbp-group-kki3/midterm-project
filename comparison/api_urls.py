from django.urls import path

from comparison import api_views

app_name = "comparison_api"

urlpatterns = [
    path("", api_views.preview, name="preview"),
    path("saved/", api_views.saved_list, name="saved_list"),
    path("saved/<int:pk>/", api_views.saved_detail, name="saved_detail"),
]
