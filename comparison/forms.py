from django import forms
from .models import SavedComparison

class SavedComparisonForm(forms.ModelForm):
    selection = forms.CharField(widget=forms.HiddenInput())

    class Meta:
        model = SavedComparison
        fields = ["name", "notes"]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "input",
                    "placeholder": "e.g. UHT milk comparison",
                    "autofocus": True,
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "input",
                    "placeholder": (
                        "Add a note about these products (optional)"
                    ),
                    "rows": 3,
                }
            ),
        }

        error_messages = {
            "name": {
                "required": "Enter a comparison name.",
            },
        }
