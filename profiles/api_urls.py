from django.urls import path
from profiles import api_views

urlpatterns = [
    path("", api_views.api_auth_root, name="api_auth_root"),
    path("login/", api_views.api_login, name="api_login"),
    path("register/", api_views.api_register, name="api_register"),
    path("logout/", api_views.api_logout, name="api_logout"),
    path("profile/", api_views.api_profile, name="api_profile"),
    path("saved/", api_views.api_saved_list, name="api_saved_list"),
    path(
        "saved/<str:item_type>/<int:pk>/remove/",
        api_views.api_saved_remove,
        name="api_saved_remove",
    ),
]