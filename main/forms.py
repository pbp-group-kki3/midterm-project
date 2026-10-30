# change: Discover's search and filters checked by a Django form, instead of reading request.GET by hand in the view.
# It's a forms.Form (not a ModelForm) because filters aren't saved in the database, they live in the address (?grade=A...).
# Same idea as meal plan's RecipeFilterForm.
#
# One rule for the whole form: a bad value never breaks the page.
# Someone can type anything into the address bar (?grade=Z, ?show=abc), so bad values are DROPPED
# or replaced by the DEFAULT, and the form is always valid. The view can trust cleaned_data.
from django import forms

from main.services.filters import ALLERGEN_TAGS, LABEL_RULES
from main.services.openfoodfacts import clean_query

GRADE_OPTIONS = ["A", "B", "C", "D", "E"]   # SpoonFeed grades (also used by views.py for the filter panel)
PAGE_STEP = 6                               # cards shown at first, and how many more "Load more" adds (Figma shows 6)
MAX_SHOW = 240                              # 40 x "Load more" is plenty, stops silly numbers like ?show=999999


# Many values allowed (?grade=A&grade=B). Unknown ones are dropped one by one, the good ones stay
class KeepValidMultipleChoiceField(forms.MultipleChoiceField):
    def clean(self, value):
        value = [v for v in (value or []) if self.valid_value(v)]
        return super().clean(value)


# One value allowed (?sort=grade). Anything unknown becomes the default
class ChoiceWithDefaultField(forms.ChoiceField):
    def __init__(self, *, default, **kwargs):
        self.default = default
        super().__init__(required=False, **kwargs)

    def clean(self, value):
        if not self.valid_value(value):
            value = self.default
        return super().clean(value)


# A whole number in a range (?show=12). Not a number / out of range / missing -> the default
class NumberWithDefaultField(forms.IntegerField):
    def __init__(self, *, default, **kwargs):
        self.default = default
        super().__init__(required=False, **kwargs)

    def clean(self, value):
        try:
            number = super().clean(value)          # IntegerField checks it's a number between min and max
        except forms.ValidationError:
            return self.default
        return self.default if number is None else number


class DiscoverFilterForm(forms.Form):
    q = forms.CharField(required=False)
    grade = KeepValidMultipleChoiceField(required=False, choices=[(g, g) for g in GRADE_OPTIONS])
    # the choices come from filters.py, so the form accepts exactly what the filter code understands
    # (including "palm_oil_free" from the "No palm oil" quick chip)
    label = KeepValidMultipleChoiceField(required=False, choices=[(key, key) for key in LABEL_RULES])
    avoid = KeepValidMultipleChoiceField(required=False, choices=[(key, key) for key in ALLERGEN_TAGS])
    processing = ChoiceWithDefaultField(default="any", choices=[("any", "Any"), ("not_ultra", "Not ultra-processed")])
    sort = ChoiceWithDefaultField(default="", choices=[("", "Relevance"), ("grade", "Best grade")])
    show = NumberWithDefaultField(default=PAGE_STEP, min_value=PAGE_STEP, max_value=MAX_SHOW)

    # clean_<field> runs after the field's own check: no HTML tags, no extra spaces, max 100 characters (step 1)
    def clean_q(self):
        return clean_query(self.cleaned_data.get("q", ""))
