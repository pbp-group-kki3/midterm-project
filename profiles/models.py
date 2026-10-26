from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    email = models.TextField(blank=True)
    location = models.CharField(max_length=100, blank=True)


    def __str__(self):
        return self.user.username