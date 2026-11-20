"""
Test URL configuration for the Food of the Day module.

Imports full project urlpatterns so that cross-app reverse lookups
(such as 'profile_saved', 'login', etc.) resolve correctly during isolated unit testing.
"""

from midterm_project.urls import urlpatterns

