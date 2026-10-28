"""
URL configuration for midterm_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from midterm_project.placeholders import coming_soon, modules
from midterm_project.styleguide import styleguide
from django.contrib.auth.views import LoginView, LogoutView
from profiles.views import register_view, profile_view, profile_edit, profile_delete, profile_picture_delete

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),

    path('modules/', modules),

    path('styleguide/', styleguide),

    path('meal-plan/', coming_soon, {'slug': 'meal-plan'}),

    path('compare/', coming_soon, {'slug': 'compare'}),

    path('food-of-the-day/', include('food_of_the_day.urls')),

    path('blog/', coming_soon, {'slug': 'blog'}),

    path('register/', register_view, name='register'),
    path('login/', LoginView.as_view(template_name='profiles/login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    
    path('profile/', profile_view, name='profile'),
    path('profile/edit/', profile_edit, name='profile_edit'),
    path('profile/delete/', profile_delete, name='profile_delete'),
    path('profile/picture/delete/', profile_picture_delete, name='profile_picture_delete'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)