from django.http import Http404
from django.shortcuts import render

MODULES = {
    'meal-plan': {'title': 'Meal Plan', 'blurb': 'Meals planned around your diet and goals.'},
    'compare': {'title': 'Compare', 'blurb': 'Put products side by side and see which one wins.'},
    'food-of-the-day': {'title': 'Food of the Day', 'blurb': 'One sustainable pick, every day.'},
    'blog': {'title': 'Blog', 'blurb': 'Stories and tips for eating a little greener.'},
    'profiles': {'title': 'Profile', 'blurb': 'Your account and food preferences.'},
}


def coming_soon(request, slug):
    module = MODULES.get(slug)
    if module is None:
        raise Http404
    return render(request, 'placeholders/coming_soon.html', module)


def modules(request):
    return render(request, 'placeholders/modules.html')
