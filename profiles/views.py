# IMPORTS
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError

# REGISTER VIEW
def register_view(request):
    errors = {}
    
    if request.method == 'POST':
        # GET SUBMITTED DATA
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        # BACKEND VALIDATION CHECKS
        if User.objects.filter(username=username).exists():
            errors['username'] = "This username is already taken."
        
        if User.objects.filter(email=email).exists():
            errors['email'] = "This email is already registered."
            
        if len(password) < 8:
            errors['password'] = "Password must be at least 8 characters long."
            
        if password != confirm_password:
            errors['confirm_password'] = "Passwords do not match."

        # IF NO ERRORS, CREATE ACCOUNT
        if not errors:
            user = User.objects.create_user(username=username, email=email, password=password)
            profile = user.profile
            
            # PARSE MULTI-SELECT DIET
            diet_str = request.POST.get('diet', '')
            if diet_str and diet_str != 'none':
                profile.diet = [d.strip() for d in diet_str.split(',') if d.strip()]
            else:
                profile.diet = []

            # PARSE ALLERGIES
            allergies_str = request.POST.get('allergies', '')
            if allergies_str:
                profile.allergies = [a.strip() for a in allergies_str.split(',') if a.strip()]

            if 'picture' in request.FILES:
                profile.profile_picture = request.FILES['picture']
                
            profile.save()
            login(request, user)
            return redirect('profile')
            
        # RETURN ERRORS AND RETAIN DATA IF VALIDATION FAILS
        return render(request, 'profiles/register.html', {'errors': errors, 'data': request.POST})
        
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
        action = request.POST.get('action')

        # 1. SAVE ACCOUNT INFO ONLY
        if action == 'update_account':
            profile.full_name = request.POST.get('full_name', '')
            profile.date_of_birth = request.POST.get('date_of_birth', '')
            profile.domicile = request.POST.get('domicile', '')

            if 'profile_picture' in request.FILES:
                profile.profile_picture = request.FILES['profile_picture']

            profile.save()
            messages.success(request, "Account information updated successfully.")

        # 2. SAVE PREFERENCES ONLY
        elif action == 'update_preferences':
            # PARSE MULTI-SELECT DIET
            diet_str = request.POST.get('diet', '')
            if diet_str and diet_str != 'none':
                profile.diet = [d.strip() for d in diet_str.split(',') if d.strip()]
            else:
                profile.diet = []
            
            calorie_target = request.POST.get('calorie_target')
            profile.calorie_target = int(calorie_target) if calorie_target else None

            allergies_str = request.POST.get('allergies', '')
            profile.allergies = [a.strip() for a in allergies_str.split(',') if a.strip()]

            profile.save()
            messages.success(request, "Preferences updated successfully.")

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

# CHANGE PASSWORD VIEW
@login_required
def change_password_view(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not request.user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")
            return redirect('profile')

        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return redirect('profile')

        try:
            validate_password(new_password, request.user)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return redirect('profile')

        request.user.set_password(new_password)
        request.user.save()
        update_session_auth_hash(request, request.user)
        
        messages.success(request, "Password changed successfully.")
        
    return redirect('profile')