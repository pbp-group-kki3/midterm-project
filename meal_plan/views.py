from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as date_format
from django.views.decorators.http import require_POST

from meal_plan.constants import (
    ALLERGY_CHIPS,
    ALLERGY_NAMES,
    ALWAYS_SHOWN_ALLERGIES,
    DEFAULT_CALORIES,
    DEFAULT_DAYS,
    DIET_CHIP_CHOICES,
    DIET_LABELS,
    HALAL_BADGE,
    MAX_DAYS,
    MAX_RECIPE_PAGES,
    MEAL_FILTER_CHOICES,
    MIN_DAYS,
    RECIPES_PER_PAGE,
)
from meal_plan.forms import MealPlanForm, RecipeFilterForm
from meal_plan.models import MealPlan, MealPlanEntry
from meal_plan.services import planner
from meal_plan.services.spoonacular import SpoonacularError

LOGIN_URL = 'login'
OFFERS_KEY = 'meal_plan_offers'
MAX_REMEMBERED_OFFERS = 20
MAX_SWAP_ROUNDS = 50


def _bounded_int(value, default, lowest, highest):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(number, lowest), highest)


def _select_options(choices, selected, helpers=None):
    helpers = helpers or {}
    values = [str(value) for value, _ in choices]
    selected = str(selected) if str(selected) in values else values[0]
    return [
        {'value': value, 'label': label, 'helper': helpers.get(value, ''), 'selected': str(value) == selected}
        for value, label in choices
    ]


def _count_text(shown, total):
    return f'{shown:,} of {total:,} recipes match your filters.'


def _plan_url(plan, day=None):
    url = reverse('meal_plan:plan_detail', args=[plan.pk])
    return f'{url}#day-{day}' if day else url


def _allergy_chips(form, profile_keys):
    selected = form['allergies'].value() or []
    shown = list(ALWAYS_SHOWN_ALLERGIES)
    for key in list(profile_keys) + list(selected):
        if key in ALLERGY_CHIPS and key not in shown:
            shown.append(key)
    return [
        {'key': key, 'label': ALLERGY_CHIPS[key], 'name': ALLERGY_NAMES[key], 'checked': key in selected}
        for key in shown
    ]


def _diet_chips(selected):
    selected = selected or []
    return [{'key': key, 'label': label, 'checked': key in selected} for key, label in DIET_CHIP_CHOICES]


def _as_date(value):
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').date()
    except ValueError:
        return None


def _plan_summary(form, profile_target):
    days = _bounded_int(form['days'].value(), DEFAULT_DAYS, MIN_DAYS, MAX_DAYS)
    selected = form['allergies'].value() or []
    diets = form['diet'].value() or []
    goal = _bounded_int(form['calorie_goal'].value(), None, 1, 100000)
    if goal:
        calories = f'{goal:,} kcal/day (your goal)'
    elif profile_target:
        calories = f'{profile_target:,} kcal/day (from your profile)'
    else:
        calories = f'{DEFAULT_CALORIES:,} kcal/day (general reference)'
    duration = '1 day' if days == 1 else f'{days} days'
    start = _as_date(form['start_date'].value())
    if start:
        dates = date_format(start, 'j M')
        if days > 1:
            dates = f"{dates} – {date_format(start + timedelta(days=days - 1), 'j M')}"
        duration = f'{duration} · {dates}'
    names = [ALLERGY_NAMES[key] for key in selected if key in ALLERGY_NAMES]
    return {
        'duration': duration,
        'meals': 'Breakfast, lunch, dinner, snack' if form['include_snack'].value() else 'Breakfast, lunch, dinner',
        'diet': ', '.join(label for key, label in DIET_CHIP_CHOICES if key in diets) or DIET_LABELS['none'],
        'avoiding': ', '.join(names) if names else 'Nothing selected',
        'calories': calories,
    }


def _remember_offers(request, entry, options):
    offers = dict(request.session.get(OFFERS_KEY, {}))
    offers.pop(str(entry.pk), None)
    offers[str(entry.pk)] = [card['id'] for card in options]
    while len(offers) > MAX_REMEMBERED_OFFERS:
        offers.pop(next(iter(offers)))
    request.session[OFFERS_KEY] = offers


@login_required(login_url=LOGIN_URL)
def plan_list(request):
    plans = list(request.user.meal_plans.all())
    context = {'plans': plans}
    if not plans:
        defaults = planner.profile_defaults(request.user)
        context['profile'] = {
            'diet_labels': [DIET_LABELS[key] for key in defaults['diets']],
            'allergies': defaults['allergy_labels'],
        }
    return render(request, 'meal_plan/plan_list.html', context)


@login_required(login_url=LOGIN_URL)
def plan_create(request):
    defaults = planner.profile_defaults(request.user)
    if request.method == 'POST':
        form = MealPlanForm(request.POST)
        if form.is_valid():
            try:
                plan = planner.create_plan(request.user, form.cleaned_data)
            except (planner.PlanError, SpoonacularError) as error:
                form.add_error(None, error.message)
            else:
                if form.cleaned_data['include_snack'] and not plan.include_snack:
                    messages.warning(request, "We couldn't add snacks right now, so this plan has no snacks.")
                messages.success(request, f'“{plan.name}” is ready.')
                return redirect(_plan_url(plan))
    else:
        form = MealPlanForm(initial={
            'start_date': timezone.localdate(),
            'days': DEFAULT_DAYS,
            'diet': defaults['diets'],
            'allergies': defaults['allergies'],
            'include_snack': defaults['include_snack'],
        })
    context = {
        'form': form,
        'allergy_chips': _allergy_chips(form, defaults['allergies']),
        'diet_chips': _diet_chips(form['diet'].value()),
        'summary': _plan_summary(form, defaults['calorie_target']),
        'profile_target': defaults['calorie_target'] or '',
        'default_calories': DEFAULT_CALORIES,
    }
    return render(request, 'meal_plan/plan_form.html', context)


@login_required(login_url=LOGIN_URL)
def plan_detail(request, pk):
    plan = get_object_or_404(MealPlan, pk=pk, user=request.user)
    days, error = planner.plan_days(plan)
    context = {
        'plan': plan,
        'days': days,
        'error_message': error.message if error else '',
        'halal_badge': HALAL_BADGE,
        'halal_note': 'halal' in plan.diet_keys,
    }
    return render(request, 'meal_plan/plan_detail.html', context)


@login_required(login_url=LOGIN_URL)
@require_POST
def plan_delete(request, pk):
    plan = get_object_or_404(MealPlan, pk=pk, user=request.user)
    name = plan.name
    plan.delete()
    messages.success(request, f'“{name}” was deleted.')
    return redirect('meal_plan:plan_list')


@login_required(login_url=LOGIN_URL)
def meal_replace(request, pk, entry_pk):
    plan = get_object_or_404(MealPlan, pk=pk, user=request.user)
    entry = get_object_or_404(MealPlanEntry, pk=entry_pk, plan=plan)
    if request.method == 'POST':
        return _choose_replacement(request, plan, entry)
    round_number = _bounded_int(request.GET.get('round'), 0, 0, MAX_SWAP_ROUNDS)
    error_message = ''
    try:
        current, options = planner.replacement_options(plan, entry, round_number)
    except SpoonacularError as error:
        current, options = planner.cached_card(entry.recipe_id), []
        error_message = error.message
    _remember_offers(request, entry, options)
    partial = request.GET.get('partial') == '1'
    query = f'?round={round_number + 1}'
    context = {
        'plan': plan,
        'entry': entry,
        'current': current,
        'options': options,
        'fit_text': planner.plan_fit_text(plan, current),
        'error_message': error_message,
        'partial': partial,
        'more_url': reverse('meal_plan:meal_replace', args=[plan.pk, entry.pk]) + query,
        'back_url': _plan_url(plan, entry.day),
    }
    template = 'meal_plan/includes/replace_panel.html' if partial else 'meal_plan/replace_meal.html'
    return render(request, template, context)


def _choose_replacement(request, plan, entry):
    offers = request.session.get(OFFERS_KEY, {})
    recipe_id = _bounded_int(request.POST.get('recipe_id'), None, 1, 10 ** 9)
    if recipe_id is None or recipe_id not in offers.get(str(entry.pk), []):
        messages.warning(request, 'That recipe is no longer on offer. Please pick again.')
        return redirect(_plan_url(plan, entry.day))
    entry.recipe_id = recipe_id
    entry.save(update_fields=['recipe_id'])
    offers = dict(offers)
    offers.pop(str(entry.pk), None)
    request.session[OFFERS_KEY] = offers
    messages.success(request, f'{entry.get_slot_display()} on day {entry.day} was replaced.')
    return redirect(_plan_url(plan, entry.day))


@login_required(login_url=LOGIN_URL)
def recipes(request):
    params = request.GET.copy()
    params.pop('page', None)
    params.pop('partial', None)
    form = RecipeFilterForm(params or None)
    page = _bounded_int(request.GET.get('page'), 1, 1, MAX_RECIPE_PAGES)
    partial = request.GET.get('partial') == '1'
    cards, total, error_message = [], 0, ''
    filters = {}
    valid = not form.is_bound or form.is_valid()
    if form.is_bound and valid:
        filters = form.cleaned_data
    reached_end = False
    if valid:
        try:
            for number in ([page] if partial else range(1, page + 1)):
                page_cards, total = planner.browse_recipes(filters, number)
                cards.extend(page_cards)
                if len(page_cards) < RECIPES_PER_PAGE:
                    reached_end = True
                    break
        except SpoonacularError as error:
            error_message = error.message
    shown = (page - 1) * RECIPES_PER_PAGE + len(cards) if partial else len(cards)
    total = max(total, shown)
    has_more = valid and not error_message and not reached_end and total > shown and page < MAX_RECIPE_PAGES
    next_params = params.copy()
    next_params['page'] = page + 1
    next_url = f'{reverse("meal_plan:recipes")}?{next_params.urlencode()}' if has_more else ''
    halal = 'halal' in (filters.get('diet') or [])
    if partial:
        html = render_to_string('meal_plan/includes/recipe_cards.html', {'cards': cards, 'halal': halal}, request=request)
        return JsonResponse({
            'html': html,
            'next_url': next_url,
            'count': _count_text(shown, total),
            'error': error_message,
        })
    context = {
        'form': form,
        'meal_options': _select_options(MEAL_FILTER_CHOICES, form['meal'].value(), {}),
        'diet_chips': _diet_chips(form['diet'].value()),
        'cards': cards,
        'count_text': _count_text(shown, total),
        'next_url': next_url,
        'error_message': error_message,
        'halal': halal,
    }
    return render(request, 'meal_plan/recipes.html', context)
