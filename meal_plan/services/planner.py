import re
from urllib.parse import urlparse

from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils.text import slugify

from meal_plan.constants import (
    ALLERGY_FROM_WORD,
    ALLERGY_WORDS,
    DEFAULT_CALORIES,
    DEFAULT_DIET,
    DIET_LABELS,
    HALAL_EXCLUDE,
    HALAL_PLAN_NOTE,
    MAIN_DIET_ORDER,
    MAX_CALORIES,
    MIN_CALORIES,
    RECIPES_PER_PAGE,
    SEARCH_TYPES,
    SLOTS,
    SNACK,
    SNACK_SHARE,
    SPOONACULAR_DIETS,
    SWAP_CANDIDATES,
    SWAP_OPTIONS,
    WEEKDAYS,
)
from meal_plan.models import MealPlan, MealPlanEntry
from meal_plan.services import spoonacular
from meal_plan.services.spoonacular import CACHE_SECONDS, SpoonacularError
from profiles.services import get_preferences

NO_PLAN_MESSAGE = (
    "Spoonacular couldn't build a plan with these choices. "
    'Try removing an allergy or choosing another diet.'
)


class PlanError(Exception):
    def __init__(self, message=NO_PLAN_MESSAGE):
        super().__init__(message)
        self.message = message


def _positive_int(value):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _profile_value(user, name):
    try:
        return getattr(user.profile, name, None)
    except (ObjectDoesNotExist, AttributeError):
        return None


def profile_calorie_target(user):
    target = _positive_int(_profile_value(user, 'calorie_target'))
    if target is None or not MIN_CALORIES <= target <= MAX_CALORIES:
        return None
    return target


def profile_diets(prefs):
    value = prefs.get('diet')
    if isinstance(value, str):
        value = value.split(',')
    if not isinstance(value, (list, tuple)):
        return []
    chosen = {item.strip().lower() for item in value if isinstance(item, str)}
    return [key for key in DIET_LABELS if key != DEFAULT_DIET and key in chosen]


def main_diet(diets):
    return next((key for key in MAIN_DIET_ORDER if key in diets), DEFAULT_DIET)


def profile_is_halal(user):
    return 'halal' in profile_diets(get_preferences(user))


def profile_defaults(user):
    prefs = get_preferences(user)
    diets = profile_diets(prefs)
    allergies = []
    for word in prefs.get('spoonacular_intolerances') or []:
        key = ALLERGY_FROM_WORD.get(word)
        if key and key not in allergies:
            allergies.append(key)
    meals_per_day = _positive_int(_profile_value(user, 'meals_per_day')) or len(SLOTS)
    return {
        'diet': main_diet(diets),
        'diets': diets,
        'allergies': allergies,
        'allergy_labels': [str(label) for label in prefs.get('allergies') or []],
        'calorie_target': profile_calorie_target(user),
        'include_snack': meals_per_day > len(SLOTS),
    }


def daily_goal(goal, user):
    if goal:
        return goal, 'goal'
    target = profile_calorie_target(user)
    if target:
        return target, 'profile'
    return DEFAULT_CALORIES, 'default'


def plan_filters(diet, allergies, prefs=None, halal=False):
    intolerances = []
    for key in allergies:
        for word in ALLERGY_WORDS.get(key, []):
            if word not in intolerances:
                intolerances.append(word)
    halal = halal or diet == 'halal'
    if prefs:
        for word in prefs.get('spoonacular_intolerances') or []:
            if word not in intolerances:
                intolerances.append(word)
        halal = halal or 'halal' in profile_diets(prefs)
    return {
        'diet': SPOONACULAR_DIETS.get(diet, ''),
        'intolerances': intolerances,
        'exclude': list(HALAL_EXCLUDE) if halal else [],
    }


def _search_params(slot, filters):
    return {
        'type': SEARCH_TYPES.get(slot, ''),
        'diet': filters['diet'],
        'intolerances': filters['intolerances'],
        'excludeIngredients': filters['exclude'],
        'addRecipeInformation': True,
        'addRecipeNutrition': True,
    }


def _nutrient_amounts(recipe):
    nutrition = recipe.get('nutrition')
    if not isinstance(nutrition, dict):
        return {}
    amounts = {}
    for item in nutrition.get('nutrients') or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip().lower()
        try:
            amount = float(item.get('amount'))
        except (TypeError, ValueError):
            continue
        amounts.setdefault(name, amount)
    return amounts


def _safe_url(url):
    if not isinstance(url, str) or not url.strip():
        return ''
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme in ('http', 'https') and parsed.netloc:
        return url
    return ''


def _image_type(recipe):
    image_type = recipe.get('imageType')
    if image_type:
        return image_type
    match = re.search(r'\.([a-zA-Z]{3,4})$', str(recipe.get('image') or ''))
    return match.group(1) if match else ''


def _labels(recipe):
    diets = [str(diet).lower() for diet in recipe.get('diets') or [] if isinstance(diet, str)]
    labels = []
    if recipe.get('vegan') or 'vegan' in diets:
        labels.append('Vegan')
    elif recipe.get('vegetarian') or 'lacto ovo vegetarian' in diets:
        labels.append('Vegetarian')
    elif 'pescatarian' in diets:
        labels.append('Pescatarian')
    if recipe.get('glutenFree') or 'gluten free' in diets:
        labels.append('Gluten free')
    if recipe.get('dairyFree') or 'dairy free' in diets:
        labels.append('Dairy free')
    if 'ketogenic' in diets:
        labels.append('Ketogenic')
    return labels[:2]


def _join(parts):
    return ' · '.join(part for part in parts if part)


def _servings_text(servings):
    if not servings:
        return ''
    return '1 serving' if servings == 1 else f'{servings} servings'


def _grams(value, decimals=1):
    if value is None:
        return ''
    return f'{value:.{decimals}f} g'


def card_from_recipe(recipe, complete=True):
    recipe_id = _positive_int(recipe.get('id'))
    title = str(recipe.get('title') or 'Untitled recipe').strip()[:200]
    amounts = _nutrient_amounts(recipe)
    calories = amounts.get('calories')
    calories = round(calories) if calories is not None else None
    protein = amounts.get('protein')
    carbs = amounts.get('carbohydrates')
    fat = amounts.get('fat')
    minutes = _positive_int(recipe.get('readyInMinutes'))
    servings = _positive_int(recipe.get('servings'))
    image_type = _image_type(recipe)
    source_url = (
        _safe_url(recipe.get('sourceUrl'))
        or _safe_url(recipe.get('spoonacularSourceUrl'))
        or f'https://spoonacular.com/recipes/{slugify(title) or "recipe"}-{recipe_id}'
    )
    minutes_text = f'{minutes} min' if minutes else ''
    calories_text = f'{calories:,} kcal' if calories is not None else ''
    protein_whole = f'P {round(protein)} g' if protein is not None else ''
    macros = ''
    if None not in (protein, carbs, fat):
        macros = _join([f'P {_grams(protein)}', f'C {_grams(carbs)}', f'F {_grams(fat)}'])
    return {
        'id': recipe_id,
        'title': title,
        'image_url': spoonacular.image_url(recipe_id, image_type) if image_type else '',
        'ready_in_minutes': minutes,
        'servings': servings,
        'calories': calories,
        'calories_label': calories_text,
        'protein': round(protein, 1) if protein is not None else None,
        'carbs': round(carbs, 1) if carbs is not None else None,
        'fat': round(fat, 1) if fat is not None else None,
        'source_name': str(recipe.get('sourceName') or '').strip()[:100],
        'source_url': source_url,
        'labels': _labels(recipe),
        'meal_meta': _join([minutes_text, calories_text]),
        'macros': macros,
        'grid_meta': _join([minutes_text, _servings_text(servings)]),
        'grid_nutrition': _join([calories_text, protein_whole]),
        'option_meta': _join([minutes_text, calories_text, protein_whole]),
        'complete': complete and calories is not None,
        'available': True,
    }


def unavailable_card(recipe_id):
    return {
        'id': recipe_id,
        'title': 'Recipe details are not available right now',
        'image_url': '',
        'calories': None,
        'calories_label': '',
        'source_url': '',
        'source_name': '',
        'labels': [],
        'meal_meta': '',
        'macros': '',
        'grid_meta': '',
        'grid_nutrition': '',
        'option_meta': '',
        'complete': False,
        'available': False,
    }


def _card_key(recipe_id):
    return f'spoon:card:{recipe_id}'


def _remember(card):
    if card['complete'] or not (cache.get(_card_key(card['id'])) or {}).get('complete'):
        cache.set(_card_key(card['id']), card, CACHE_SECONDS)
    return card


def recipe_cards(recipe_ids):
    ids = []
    for value in recipe_ids:
        recipe_id = _positive_int(value)
        if recipe_id is not None and recipe_id not in ids:
            ids.append(recipe_id)
    cards = {}
    pending = []
    for recipe_id in ids:
        card = cache.get(_card_key(recipe_id))
        if card and card.get('complete'):
            cards[recipe_id] = card
        else:
            pending.append(recipe_id)
    error = None
    if pending:
        recipes, error = spoonacular.get_recipes(pending)
        for recipe_id in pending:
            recipe = recipes.get(recipe_id)
            if recipe is not None:
                cards[recipe_id] = _remember(card_from_recipe(recipe))
            else:
                cards[recipe_id] = cache.get(_card_key(recipe_id)) or unavailable_card(recipe_id)
    return cards, error


def cached_card(recipe_id):
    recipe = spoonacular.get_cached_recipe(recipe_id)
    if recipe is not None:
        return card_from_recipe(recipe)
    return cache.get(_card_key(recipe_id))


def closest_by_calories(cards, target):
    if target is None:
        return list(cards)
    return sorted(cards, key=lambda card: (card['calories'] is None, abs((card['calories'] or 0) - target)))


def _valid_meals(meals):
    if not isinstance(meals, list):
        return []
    return [meal for meal in meals if spoonacular.is_recipe(meal)]


def _generate_days(days, calories, filters, request_key=''):
    exclude = filters['intolerances'] + filters['exclude']
    if days == 1:
        data = spoonacular.generate_meal_plan('day', calories, filters['diet'], exclude, f'{request_key}:0')
        day_meals = [data.get('meals') if isinstance(data, dict) else None]
    else:
        day_meals = []
        week_number = 0
        while len(day_meals) < days:
            data = spoonacular.generate_meal_plan('week', calories, filters['diet'], exclude, f'{request_key}:{week_number}')
            week = data.get('week') if isinstance(data, dict) else None
            if not isinstance(week, dict):
                raise PlanError()
            for name in WEEKDAYS:
                day = week.get(name)
                day_meals.append(day.get('meals') if isinstance(day, dict) else None)
            week_number += 1
    result = []
    for meals in day_meals[:days]:
        valid = _valid_meals(meals)[:len(SLOTS)]
        if len(valid) < len(SLOTS):
            raise PlanError()
        for meal in valid:
            _remember(card_from_recipe(meal, complete=False))
        result.append(valid)
    return result


def _pick_snacks(days, calories, filters, request_key=''):
    params = _search_params(SNACK, filters)
    params.update({'sort': 'random', 'number': min(max(days * 2, SWAP_CANDIDATES), 30)})
    try:
        data = spoonacular.search_recipes(params, cache_variant=request_key)
    except SpoonacularError:
        return []
    cards = [_remember(card_from_recipe(recipe)) for recipe in data.get('results') or [] if spoonacular.is_recipe(recipe)]
    return [card['id'] for card in closest_by_calories(cards, calories)[:days]]


def create_plan(user, data):
    days = data['days']
    goal, _ = daily_goal(data.get('calorie_goal'), user)
    allergies = list(data.get('allergies') or [])
    filters = plan_filters(data['diet'], allergies, halal=profile_is_halal(user))
    snack_calories = round(goal * SNACK_SHARE) if data.get('include_snack') else 0
    request_key = f"{user.pk}:{data['name']}:{data['start_date']}"
    meal_days = _generate_days(days, goal - snack_calories, filters, request_key)
    snacks = _pick_snacks(days, snack_calories, filters, request_key) if snack_calories else []
    with transaction.atomic():
        plan = MealPlan.objects.create(
            user=user,
            name=data['name'],
            date=data['start_date'],
            timeframe='day' if days == 1 else 'week',
            days=days,
            diet=data['diet'],
            allergies=allergies,
            include_snack=bool(snacks),
            calorie_goal=goal,
        )
        entries = []
        for number, meals in enumerate(meal_days, start=1):
            for slot, meal in zip(SLOTS, meals):
                entries.append(MealPlanEntry(plan=plan, day=number, slot=slot, recipe_id=meal['id']))
            if snacks:
                entries.append(MealPlanEntry(plan=plan, day=number, slot=SNACK, recipe_id=snacks[(number - 1) % len(snacks)]))
        MealPlanEntry.objects.bulk_create(entries)
    return plan


def plan_days(plan):
    entries = sorted(plan.entries.all(), key=lambda entry: (entry.day, entry.slot_position))
    cards, error = recipe_cards([entry.recipe_id for entry in entries])
    days = []
    for number in range(1, plan.days + 1):
        meals = [
            {'entry': entry, 'recipe': cards.get(entry.recipe_id) or unavailable_card(entry.recipe_id)}
            for entry in entries
            if entry.day == number
        ]
        known = [meal['recipe']['calories'] for meal in meals if meal['recipe'].get('calories') is not None]
        total = sum(known) if known else None
        days.append({
            'number': number,
            'date': plan.date_for(number),
            'meals': meals,
            'calories': total,
            'calories_label': f'{total:,} kcal' if total is not None else '',
        })
    return days, error


def plan_fit_text(plan, current):
    parts = []
    if plan.diet == 'halal':
        parts.append(HALAL_PLAN_NOTE)
    elif plan.diet != DEFAULT_DIET:
        parts.append(DIET_LABELS.get(plan.diet, ''))
    if current and current.get('calories') is not None:
        parts.append(f'about {current["calories"]:,} kcal')
    return ', '.join(part for part in parts if part)


def replacement_options(plan, entry, round_number=0):
    current_cards, _ = recipe_cards([entry.recipe_id])
    current = current_cards.get(entry.recipe_id)
    filters = plan_filters(plan.diet, plan.allergies, get_preferences(plan.user))
    params = _search_params(entry.slot, filters)
    params.update({'sort': 'random', 'number': SWAP_CANDIDATES})
    data = spoonacular.search_recipes(params, cache_variant=round_number)
    in_plan = set(plan.entries.values_list('recipe_id', flat=True))
    cards = [
        _remember(card_from_recipe(recipe))
        for recipe in data.get('results') or []
        if spoonacular.is_recipe(recipe) and recipe['id'] != entry.recipe_id
    ]
    target = current.get('calories') if current else None
    ordered = closest_by_calories(cards, target)
    ordered.sort(key=lambda card: card['id'] in in_plan)
    return current, [dict(card, in_plan=card['id'] in in_plan) for card in ordered[:SWAP_OPTIONS]]


def browse_recipes(filters, page=1):
    diet = filters.get('diet') or DEFAULT_DIET
    diets = [SPOONACULAR_DIETS.get(diet, '')]
    if filters.get('sustainable') and diet not in ('vegetarian', 'vegan'):
        diets.append('vegetarian')
    intolerances = []
    if filters.get('gluten_free'):
        intolerances.append('gluten')
    if filters.get('dairy_free'):
        intolerances.append('dairy')
    query = (filters.get('q') or '').strip()
    params = {
        'query': query,
        'type': SEARCH_TYPES.get(filters.get('meal') or '', ''),
        'diet': [word for word in diets if word],
        'intolerances': intolerances,
        'excludeIngredients': HALAL_EXCLUDE if diet == 'halal' else [],
        'maxCalories': filters.get('max_calories'),
        'maxReadyTime': filters.get('max_minutes'),
        'sort': '' if query else 'popularity',
        'addRecipeInformation': True,
        'addRecipeNutrition': True,
        'number': RECIPES_PER_PAGE,
        'offset': (page - 1) * RECIPES_PER_PAGE,
    }
    data = spoonacular.search_recipes(params)
    cards = [_remember(card_from_recipe(recipe)) for recipe in data.get('results') or [] if spoonacular.is_recipe(recipe)]
    total = _positive_int(data.get('totalResults')) or 0
    return cards, max(total, (page - 1) * RECIPES_PER_PAGE + len(cards))
