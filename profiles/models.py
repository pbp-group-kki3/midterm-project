# IMPORTS
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# PROFILE MODEL
class Profile(models.Model):
    # DIET CHOICES
    DIET_CHOICES = [
        ('none', 'None'),
        ('halal', 'Halal'),
        ('vegetarian', 'Vegetarian'),
        ('vegan', 'Vegan'),
        ('pescatarian', 'Pescatarian'),
    ]

    # FIELDS
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    
    # NEW PERSONAL INFO FIELDS
    full_name = models.CharField(max_length=150, blank=True)
    date_of_birth = models.CharField(max_length=20, blank=True)
    domicile = models.CharField(max_length=100, blank=True)
    
    # PREFERENCES
    diet = models.CharField(max_length=20, choices=DIET_CHOICES, default='none')
    allergies = models.JSONField(default=list, blank=True)
    calorie_target = models.IntegerField(null=True, blank=True)
    meals_per_day = models.IntegerField(default=3)

    # STRING REPRESENTATION
    def __str__(self):
        return f"{self.user.username}'s Profile"

# SIGNALS
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()