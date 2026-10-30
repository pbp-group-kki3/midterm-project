from django import forms
from .models import Article

class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'topic', 'cover_image', 'summary', 'body']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Enter an article title'}),
            'topic': forms.Select(attrs={'class': 'input'}),
            'cover_image': forms.FileInput(attrs={'class': 'hidden', 'id': 'cover_image_input', 'accept': 'image/*'}),
            'summary': forms.Textarea(attrs={'class': 'input', 'placeholder': 'Add a short description', 'rows': 3}),
            'body': forms.Textarea(attrs={'class': 'input', 'placeholder': 'Write your article here', 'rows': 10}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure title, topic, and body are required per the mockup stars
        self.fields['title'].required = True
        self.fields['topic'].required = True
        self.fields['body'].required = True
        # Summary and image are optional
        self.fields['summary'].required = False
        self.fields['cover_image'].required = False

# Validate comments and replies before they reach the database.
class ArticleCommentForm(forms.Form):
    text = forms.CharField(
        max_length=2000,
        strip=True,
        error_messages={"required": "Write a comment before posting."},
    )
    parent_id = forms.IntegerField(required=False, min_value=1)