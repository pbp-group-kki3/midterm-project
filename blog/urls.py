from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.blog_list, name="blog_list"),
    path("create/", views.article_create, name="article_create"),
    path("saved/<int:pk>/", views.saved_article_detail, name="saved_article_detail"),
    path("saved/<int:pk>/remove/", views.saved_article_remove, name="saved_article_remove"),
    path("<slug:slug>/", views.article_detail, name="article_detail"),
    path("<slug:slug>/edit/", views.article_edit, name="article_edit"),
    path("<slug:slug>/delete/", views.article_delete, name="article_delete"),
]