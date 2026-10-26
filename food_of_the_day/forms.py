from django import forms
from food_of_the_day.models import MealComment


class MealCommentForm(forms.ModelForm):
    class Meta:
        model = MealComment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'w-full p-3 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm resize-none',
                'placeholder': 'Share your thoughts, tips, or sustainable twists on this recipe...',
                'rows': 3,
                'maxlength': '1000',
                'required': True,
            })
        }
        labels = {
            'text': ''
        }
