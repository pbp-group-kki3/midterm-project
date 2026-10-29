from django import forms

from meal_plan.constants import (
    ALLERGY_CHOICES,
    DIET_CHIP_CHOICES,
    MAX_CALORIES,
    MAX_DAYS,
    MEAL_FILTER_CHOICES,
    MIN_CALORIES,
    MIN_DAYS,
    PLANT_BASED_DIETS,
)


class MealPlanForm(forms.Form):
    name = forms.CharField(
        label='Plan name',
        max_length=60,
        error_messages={'required': 'Give your plan a name.'},
        widget=forms.TextInput(attrs={'class': 'input', 'placeholder': 'e.g. Green week', 'autocomplete': 'off'}),
    )
    start_date = forms.DateField(
        label='Start date',
        error_messages={'required': 'Pick a start date.', 'invalid': 'Enter a valid date.'},
        widget=forms.DateInput(attrs={'class': 'input', 'type': 'date'}, format='%Y-%m-%d'),
    )
    days = forms.IntegerField(
        label='Number of days',
        min_value=MIN_DAYS,
        max_value=MAX_DAYS,
        help_text=f'Between {MIN_DAYS} and {MAX_DAYS} days.',
        error_messages={
            'required': f'Enter a number between {MIN_DAYS} and {MAX_DAYS}.',
            'invalid': f'Enter a number between {MIN_DAYS} and {MAX_DAYS}.',
            'min_value': f'Enter a number between {MIN_DAYS} and {MAX_DAYS}.',
            'max_value': f'Enter a number between {MIN_DAYS} and {MAX_DAYS}.',
        },
        widget=forms.NumberInput(attrs={'class': 'input', 'min': MIN_DAYS, 'max': MAX_DAYS, 'inputmode': 'numeric'}),
    )
    diet = forms.MultipleChoiceField(
        label='Diet',
        choices=DIET_CHIP_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    allergies = forms.MultipleChoiceField(
        label='Allergies and intolerances',
        choices=ALLERGY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    include_snack = forms.BooleanField(
        label='Include a snack every day',
        required=False,
    )
    calorie_goal = forms.IntegerField(
        label='Daily calorie goal (optional)',
        min_value=MIN_CALORIES,
        max_value=MAX_CALORIES,
        required=False,
        help_text='Leave empty to use the target from your profile, or 2,000 kcal if you have none.',
        error_messages={
            'invalid': f'Enter a goal between {MIN_CALORIES:,} and {MAX_CALORIES:,} kcal.',
            'min_value': f'Enter a goal between {MIN_CALORIES:,} and {MAX_CALORIES:,} kcal.',
            'max_value': f'Enter a goal between {MIN_CALORIES:,} and {MAX_CALORIES:,} kcal.',
        },
        widget=forms.NumberInput(attrs={
            'class': 'input',
            'placeholder': 'e.g. 2000',
            'min': MIN_CALORIES,
            'max': MAX_CALORIES,
            'step': 50,
            'inputmode': 'numeric',
        }),
    )

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split())
        if not name:
            raise forms.ValidationError('Give your plan a name.')
        return name

    def clean_diet(self):
        diets = self.cleaned_data['diet']
        if 'ketogenic' in diets and any(key in diets for key in PLANT_BASED_DIETS):
            raise forms.ValidationError("Ketogenic can't be combined with vegetarian, vegan or pescatarian in one plan.")
        return diets


class RecipeFilterForm(forms.Form):
    q = forms.CharField(
        label='Search',
        max_length=80,
        required=False,
        widget=forms.TextInput(attrs={'class': 'input', 'placeholder': 'e.g. oats', 'type': 'search'}),
    )
    meal = forms.ChoiceField(
        label='Meal',
        choices=MEAL_FILTER_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'input'}),
    )
    diet = forms.MultipleChoiceField(
        label='Diet',
        choices=DIET_CHIP_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    max_calories = forms.IntegerField(
        label='Max kcal',
        min_value=50,
        max_value=3000,
        required=False,
        error_messages={
            'invalid': 'Enter a number from 50 to 3,000.',
            'min_value': 'Enter a number from 50 to 3,000.',
            'max_value': 'Enter a number from 50 to 3,000.',
        },
        widget=forms.NumberInput(attrs={'class': 'input', 'placeholder': 'e.g. 600', 'min': 50, 'max': 3000, 'inputmode': 'numeric'}),
    )
    max_minutes = forms.IntegerField(
        label='Max minutes',
        min_value=5,
        max_value=600,
        required=False,
        error_messages={
            'invalid': 'Enter a number from 5 to 600.',
            'min_value': 'Enter a number from 5 to 600.',
            'max_value': 'Enter a number from 5 to 600.',
        },
        widget=forms.NumberInput(attrs={'class': 'input', 'placeholder': 'e.g. 30', 'min': 5, 'max': 600, 'inputmode': 'numeric'}),
    )
    gluten_free = forms.BooleanField(label='Gluten free', required=False)
    dairy_free = forms.BooleanField(label='Dairy free', required=False)
    sustainable = forms.BooleanField(label='Sustainable', required=False)
