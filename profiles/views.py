from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required       
from .models import Profile
from django.contrib.auth.models import User
from django.contrib.auth import login

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


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            return render(request, 'profiles/register.html', {'error': 'Passwords do not match'})

        if User.objects.filter(username=username).exists():
            return render(request, 'profiles/register.html', {'error': 'Username already taken'})
            
        user = User.objects.create_user(username=username, email=email, password=password)
        
        profile, created = Profile.objects.get_or_create(user=user)
        
        profile.dietary_preferences = request.POST.get('dietary_preferences', '')
        profile.allergies = request.POST.get('allergies', '')
        
        if 'picture' in request.FILES:
            profile.picture = request.FILES['picture']
            
        profile.save()
        login(request, user)
        return redirect('profile')

    return render(request, 'profiles/register.html')

