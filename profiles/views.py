from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib import messages
from .models import Profile

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
            profile.profile_picture = request.FILES['picture']

        profile.save()
        login(request, user)
        return redirect('profile')

    return render(request, 'profiles/register.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('profile')
        else:
            return render(request, 'profiles/login.html', {'error': 'Invalid username or password'})

    return render(request, 'profiles/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def profile_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    return render(request, 'profiles/profile.html', {'profile': profile})

@login_required
def profile_edit(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        new_username = request.POST.get('username')
        new_email = request.POST.get('email')

        if new_username and new_username != request.user.username:
            if User.objects.filter(username=new_username).exists():
                messages.error(request, "Username is already taken.")
                return redirect('profile')
            request.user.username = new_username
        
        if new_email:
            request.user.email = new_email

        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        if new_password:
            if new_password == confirm_password:
                request.user.set_password(new_password)
                update_session_auth_hash(request, request.user)
            else:
                messages.error(request, "Passwords do not match.")
                return redirect('profile')

        request.user.save()

        if 'dietary_preferences' in request.POST:
            profile.dietary_preferences = request.POST.get('dietary_preferences')
        if 'allergies' in request.POST:
            profile.allergies = request.POST.get('allergies')
        if 'nutritional_goals' in request.POST:
            profile.nutritional_goals = request.POST.get('nutritional_goals')

        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']

        profile.save()
        messages.success(request, "Profile updated successfully!")
        return redirect('profile')

    return redirect('profile')

@login_required
def profile_picture_delete(request):
    if request.method == 'POST':
        profile, created = Profile.objects.get_or_create(user=request.user)
        if profile.profile_picture:
            profile.profile_picture.delete(save=True)
            messages.success(request, "Profile picture removed.")
    return redirect('profile')

@login_required
def profile_delete(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        return redirect('/')
    return redirect('profile')