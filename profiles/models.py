from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    
    dietary_preferences = models.TextField(blank=True, help_text="e.g., Vegan, Vegetarian, Keto")
    allergies = models.TextField(blank=True, help_text="e.g., Peanuts, Gluten, Dairy")
    nutritional_goals = models.TextField(blank=True, help_text="e.g., Weight loss, Muscle gain")

    def __str__(self):
        return f"{self.user.username}'s Profile"