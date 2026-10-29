# IMPORTS
from posixpath import normpath
from urllib.parse import unquote, urlencode, urlsplit

from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from comparison.models import SavedComparison
from main.models import FavoriteProduct
from meal_plan.models import MealPlan
from profiles.forms import AccountForm, PreferencesForm, SignupForm
from profiles.preferences import normalize_allergies, normalize_diets
from profiles.saved import SAVED_CATEGORIES, saved_items

# REGISTER VIEW
# Validate signup and save the account and preferences together.
@never_cache
def register_view(request):
    # Reuse LoginView's same-host and loop checks for a signup return destination.
    login_view = ProfileLoginView()
    login_view.setup(request)
    next_url = login_view.get_redirect_url()
    if request.user.is_authenticated:
        return redirect(next_url or "main:show_main")

    if request.method == "POST":
        # Adapt the existing template's password names to UserCreationForm.
        data = request.POST.copy()
        data["password1"] = request.POST.get("password", "")
        data["password2"] = request.POST.get("confirm_password", "")
        form = SignupForm(data, request.FILES)

        form_is_valid = form.is_valid()

        # Continue validates Step 1 without creating or authenticating an account.
        if request.POST.get("validate_step") == "1":
            return JsonResponse({
                "ok": form_is_valid,
                "errors": form.errors.get_json_data(),
            }, status=200 if form_is_valid else 400)

        if form_is_valid:
            with transaction.atomic():
                user = form.save()
                profile = user.profile
                profile.diet = form.cleaned_data["diet"]
                profile.allergies = form.cleaned_data["allergies"]

                if form.cleaned_data.get("picture"):
                    profile.profile_picture = form.cleaned_data["picture"]

                profile.save()

            messages.success(request, "Your account has been created. Please log in.")
            login_url = reverse("login")
            return redirect(login_url + ("?" + urlencode({"next": next_url}) if next_url else ""))
    else:
        form = SignupForm()

    # Match Django form errors to the existing signup template field names.
    error_names = {"password1": "password", "password2": "confirm_password",
    }
    errors = {error_names.get(name, name): " ".join(field_errors) for name, field_errors in form.errors.items()}

    # Reopen the signup step containing the validation error.
    registration_step = 1

    if errors and not any(name in errors for name in ("username", "email", "password", "confirm_password")):
        registration_step = (2 if "diet" in errors or "allergies" in errors else 3)

    return render(request, "profiles/register.html", {
        "signup_form": form,
        "errors": errors,
        "data": request.POST if request.method == "POST" else {},
        "registration_step": registration_step,
        "next": next_url,
    })

# Build the shared profile context for normal pages and validation errors.
def _profile_context(
    request,
    section="account",
    account_form=None,
    preferences_form=None,
):
    profile = request.user.profile
    category = request.GET.get("category", "all")

    if category not in dict(SAVED_CATEGORIES):
        raise Http404("Unknown saved category.")

    if account_form is None:
        account_form = AccountForm(instance=profile)

    if preferences_form is None:
        preferences_form = PreferencesForm(
            instance=profile,
            initial={
                "diet": normalize_diets(profile.diet),
                "allergies": normalize_allergies(profile.allergies),
            },
        )

    # Load Saved records only while displaying the Saved section.
    records = saved_items(request.user, category) if section == "saved" else []
    saved_page = Paginator(records, 12).get_page(request.GET.get("page"))

    return {
        "profile": profile,
        "active_section": section,
        "account_form": account_form,
        "account_editing": account_form.is_bound,
        "preferences_form": preferences_form,
        "preferences_editing": preferences_form.is_bound,
        "saved_categories": SAVED_CATEGORIES,
        "saved_category": category,
        "saved_page": saved_page,
    }


# Open a directly addressable profile section for the authenticated user.
@login_required
@never_cache
@require_GET
def profile_view(request):
    section = request.GET.get("section", "account")

    if section == "saved":
        return redirect("profile_saved")

    if section not in ("account", "preferences", "history"):
        section = "account"

    return render(request, "profiles/profile.html", _profile_context(request, section=section))

# Open Saved with the category supplied in the query string.
@login_required
@never_cache
@require_GET
def profile_saved(request):
    return render(request, "profiles/profile.html", _profile_context(request, section="saved"))

# Validate account and preference updates before saving them.
@login_required
@require_POST
def profile_edit(request):
    profile = request.user.profile
    action = request.POST.get("action")

    if action == "update_account":
        form = AccountForm(
            request.POST,
            request.FILES,
            instance=profile,
            editable=True,
        )

        if form.is_valid():
            form.save()
            messages.success(request, "Account information updated successfully.")
            return redirect("profile")

        return render(
            request,
            "profiles/profile.html",
            _profile_context(request, section="account", account_form=form),
            status=400,
        )

    if action == "update_preferences":
        form = PreferencesForm(request.POST, instance=profile)

        if form.is_valid():
            form.save()
            messages.success(request, "Preferences updated successfully.")
            return redirect(reverse("profile") + "?section=preferences")

        return render(
            request,
            "profiles/profile.html",
            _profile_context(
                request,
                section="preferences",
                preferences_form=form,
            ),
            status=400,
        )
    raise Http404("Unknown profile action.")

# PROFILE PICTURE DELETE VIEW
@login_required
@require_POST
def profile_picture_delete(request):
    if request.method == 'POST':
        profile = request.user.profile
        if profile.profile_picture:
            profile.profile_picture.delete(save=True)
            messages.success(request, "Profile picture removed.")
    return redirect('profile')

# PROFILE DELETE VIEW
@login_required
@require_POST
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

@login_required
@require_POST
def profile_saved_remove(request, kind, pk):
    models = {
        "product": FavoriteProduct,
        "comparison": SavedComparison,
        "meal-plan": MealPlan,
    }
    model = models.get(kind)

    if model is None:
        raise Http404("This saved type cannot be removed here.")

    record = get_object_or_404(model, pk=pk, user=request.user)
    record.delete()

    category = request.POST.get("category", "all")

    if category not in dict(SAVED_CATEGORIES):
        category = "all"

    if kind == "meal-plan":
        messages.success(request, f"“{record.name}” was deleted.")
    else:
        messages.success(request, "Item removed from Saved.")

    return redirect(
        reverse("profile_saved")
        + "?"
        + urlencode({"category": category})
    )


# Display an owned saved comparison without replacing the active lineup.
@login_required
@never_cache
@require_GET
def profile_saved_comparison(request, pk):
    record = get_object_or_404(
        SavedComparison,
        pk=pk,
        user=request.user,
    )

    barcodes = record.barcodes

    if (
        not isinstance(barcodes, list)
        or not 2 <= len(barcodes) <= 3
        or not all(
            isinstance(barcode, str)
            and barcode.isascii()
            and barcode.isdigit()
            for barcode in barcodes
        )
    ):
        raise Http404(
            "This saved comparison has an invalid selection."
        )

    from comparison.views import compare_products
    return compare_products(request, saved_comparison=record)

# Preserve safe login returns and redirect authenticated users away from Login.
class ProfileLoginView(LoginView):
    template_name = "profiles/login.html"
    redirect_authenticated_user = True

    # Keep Django's same-host validation and reject authentication loops.
    def get_redirect_url(self):
        destination = super().get_redirect_url()

        if not destination:
            return ""

        path = urlsplit(destination).path

        if not path:
            return ""

        normalized_path = normpath(unquote(path))
        blocked_paths = {normpath(reverse("login")), normpath(reverse("logout")), normpath(reverse("register"))}

        if normalized_path in blocked_paths:
            return ""

        return destination
