import re
from django import forms
from django.core.exceptions import ValidationError
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

    def clean_text(self):
        text = self.cleaned_data.get('text', '')
        if not text:
            raise ValidationError('Comment cannot be empty.')

        # Strip null bytes and non-printable control characters (excluding newline and tab)
        cleaned_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text).strip()

        if len(cleaned_text) < 2:
            raise ValidationError('Comment is too short. Please provide at least 2 characters.')

        if len(cleaned_text) > 1000:
            raise ValidationError('Comment cannot exceed 1000 characters.')

        return cleaned_text
