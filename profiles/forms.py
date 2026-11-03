from datetime import datetime

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from profiles.models import Profile
from profiles.preferences import ALLERGY_CHOICES, DIET_CHOICES

# Helper: Attempts to parse birth dates using two common formats (ISO and DD/MM/YYYY)
def parse_birth_date(value):
    if not value:
        return None

    for date_format in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value).strip(), date_format).date()
        except ValueError:
            continue

    return None

# Helper: Generates a multiselect checkbox field for dietary choices
def diet_field():
    return forms.MultipleChoiceField(
        choices=DIET_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "profile-chip-input"}
        ),
    )

# Helper: Generates a multiselect checkbox field for allergy choices
def allergy_field():
    return forms.MultipleChoiceField(
        choices=ALLERGY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "profile-chip-input"}
        ),
    )

# Form: Handles step-by-step user registration (Credentials + Preferences + Picture)
class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    diet = diet_field()
    allergies = allergy_field()
    picture = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    # Validation: Prevents multiple accounts from using the same email address
    def clean_email(self):
        email = self.cleaned_data["email"].strip()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")

        return email

    # Validation: Removes duplicate diet selections sent from the frontend
    def clean_diet(self):
        return list(dict.fromkeys(self.cleaned_data["diet"]))

    # Validation: Removes duplicate allergy selections sent from the frontend
    def clean_allergies(self):
        return list(dict.fromkeys(self.cleaned_data["allergies"]))

# Form: Handles updating user dietary and allergy preferences in the profile dashboard
class PreferencesForm(forms.ModelForm):
    diet = diet_field()
    allergies = allergy_field()
    calorie_target = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "class": "input",
                "placeholder": "e.g. 2000",
                "min": 1,
            }
        ),
    )

    class Meta:
        model = Profile
        fields = ("diet", "allergies", "calorie_target")

    # Validation: Deduplicates diet updates
    def clean_diet(self):
        return list(dict.fromkeys(self.cleaned_data["diet"]))

    # Validation: Deduplicates allergy updates
    def clean_allergies(self):
        return list(dict.fromkeys(self.cleaned_data["allergies"]))

# Form: Handles updating personal info (Name, DOB, Location, Picture)
class AccountForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "type": "date",
                "class": "input profile-input",
            },
        ),
    )
    clear_birth_date = forms.BooleanField(
        required=False,
        label="Clear the existing unrecognized birth date",
    )

    class Meta:
        model = Profile
        fields = (
            "full_name",
            "date_of_birth",
            "domicile",
            "profile_picture",
        )
        widgets = {
            "full_name": forms.TextInput(
                attrs={"class": "input profile-input"}
            ),
            "domicile": forms.TextInput(
                attrs={"class": "input profile-input"}
            ),
        }

    # Setup: Parses existing date of birth and locks fields in read-only mode by default
    def __init__(self, *args, editable=False, **kwargs):
        super().__init__(*args, **kwargs)

        stored_date = self.instance.date_of_birth or ""
        parsed_date = parse_birth_date(stored_date)
        self.legacy_birth_date = (
            stored_date if stored_date and not parsed_date else ""
        )

        if not self.is_bound:
            self.initial["date_of_birth"] = parsed_date

        self.fields["date_of_birth"].widget.attrs["max"] = (
            timezone.localdate().isoformat()
        )

        if not editable:
            for name in ("full_name", "date_of_birth", "domicile"):
                self.fields[name].widget.attrs["disabled"] = True

    # Validation: Ensures the user isn't entering a birth date in the future
    def clean_date_of_birth(self):
        value = self.cleaned_data.get("date_of_birth")

        if value and value > timezone.localdate():
            raise forms.ValidationError(
                "Date of birth cannot be in the future."
            )

        return value

    # Validation: Forces the user to fix or clear broken legacy date strings if editing
    def clean(self):
        cleaned = super().clean()

        if cleaned.get("clear_birth_date"):
            cleaned["date_of_birth"] = None
        elif (
            self.legacy_birth_date
            and not cleaned.get("date_of_birth")
            and "date_of_birth" not in self.errors
        ):
            self.add_error(
                "date_of_birth",
                "Enter a valid birth date or explicitly clear the existing value.",
            )

        return cleaned

    # Save: Converts the Python date object into an ISO string for the database CharField
    def save(self, commit=True):
        profile = super().save(commit=False)
        birth_date = self.cleaned_data.get("date_of_birth")
        profile.date_of_birth = birth_date.isoformat() if birth_date else ""

        if commit:
            profile.save()

        return profile