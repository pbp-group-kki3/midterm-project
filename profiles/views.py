# IMPORTS
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages

# REGISTER VIEW
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile = user.profile
            
            profile.diet = request.POST.get('diet', 'none')
            allergies_str = request.POST.get('allergies', '')
            if allergies_str:
                profile.allergies = [a.strip() for a in allergies_str.split(',') if a.strip()]

            if 'picture' in request.FILES:
                profile.profile_picture = request.FILES['picture']
                
            profile.save()
            login(request, user)
            return redirect('profile')
        else:
            messages.error(request, "Registration failed. Check password requirements.")
            return render(request, 'profiles/register.html', {'error': 'Invalid registration data.'})
            
    return render(request, 'profiles/register.html')

# PROFILE VIEW
@login_required
def profile_view(request):
    return render(request, 'profiles/profile.html', {'profile': request.user.profile})

# PROFILE EDIT VIEW
@login_required
def profile_edit(request):
    profile = request.user.profile

    if request.method == 'POST':
        profile.diet = request.POST.get('diet', 'none')
        
        calorie_target = request.POST.get('calorie_target')
        profile.calorie_target = int(calorie_target) if calorie_target else None
        
        meals_per_day = request.POST.get('meals_per_day')
        if meals_per_day:
            profile.meals_per_day = int(meals_per_day)

        allergies_str = request.POST.get('allergies', '')
        profile.allergies = [a.strip() for a in allergies_str.split(',') if a.strip()]

        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']

        profile.save()
        messages.success(request, "Preferences updated successfully.")
        return redirect('profile')

    return redirect('profile')

# PROFILE PICTURE DELETE VIEW
@login_required
def profile_picture_delete(request):
    if request.method == 'POST':
        profile = request.user.profile
        if profile.profile_picture:
            profile.profile_picture.delete(save=True)
            messages.success(request, "Profile picture removed.")
    return redirect('profile')

# PROFILE DELETE VIEW
@login_required
def profile_delete(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        return redirect('/')
    return redirect('profile')