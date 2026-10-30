from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.blog_list, name='blog_list'),
    path('create/', views.article_create, name='article_create'),
    path('<slug:slug>/', views.article_detail, name='article_detail'),
    path('<slug:slug>/edit/', views.article_edit, name='article_edit'),
    path('<slug:slug>/delete/', views.article_delete, name='article_delete'),
]