from urllib import request

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required       
from .models import Profile

@login_required
def profile_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        profile.dietary_preferences = request.POST.get('dietary_preferences', '')
        profile.allergies = request.POST.get('allergies', '')
        profile.nutritional_goals = request.POST.get('nutritional_goals', '')

        email = request.POST.get('email', '')
        if email:
            request.user.email = email
            request.user.save()

        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']


        profile.save()
        return redirect('profile_view') 

    return render(request, 'profiles/profile.html', {'profile': profile})


