# IMPORTS
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# PROFILE MODEL: Extends the default Django User model with custom app-specific fields
class Profile(models.Model):
    # DIET CHOICES
    DIET_CHOICES = [
        ('none', 'None'),
        ('halal', 'Halal'),
        ('vegetarian', 'Vegetarian'),
        ('vegan', 'Vegan'),
        ('pescatarian', 'Pescatarian'),
    ]

    # Core relationship to Django's Auth User and the avatar image field
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    
    # Personal identity fields
    full_name = models.CharField(max_length=150, blank=True)
    date_of_birth = models.CharField(max_length=20, blank=True)
    domicile = models.CharField(max_length=100, blank=True)
    
    # User app preferences stored as JSON arrays for flexibility
    diet = models.JSONField(default=list, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    calorie_target = models.IntegerField(null=True, blank=True)
    meals_per_day = models.IntegerField(default=3)

    # String representation for the Django Admin panel
    def __str__(self):
        return f"{self.user.username}'s Profile"

# SIGNAL: Automatically creates a Profile record in the DB whenever a new User is registered
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

# SIGNAL: Automatically saves the Profile record whenever the User is saved
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()