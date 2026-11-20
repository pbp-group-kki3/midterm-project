from django.urls import path
from blog import api_views

app_name = "blog_api"  # Use a distinct namespace so it doesn't clash with app_name = "blog"

urlpatterns = [
    path("saved/", api_views.api_saved_list, name="api_saved_list"),
    path("saved/<int:pk>/", api_views.api_saved_detail_remove, name="api_saved_detail_remove"),
    path("articles/", api_views.api_article_list_create, name="api_article_list_create"),
    path("articles/<slug:slug>/", api_views.api_article_detail, name="api_article_detail"),
    path("articles/<slug:slug>/save/", api_views.api_article_save_toggle, name="api_article_save_toggle"),
    path("articles/<slug:slug>/comments/", api_views.api_article_comment_create, name="api_article_comment_create"),
    path(
        "articles/<slug:slug>/comments/<int:comment_id>/like/",
        api_views.api_comment_like,
        name="api_comment_like",
    ),
]