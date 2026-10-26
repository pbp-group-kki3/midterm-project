import os
import requests
from django.core.cache import cache

try:
    from meal_plan.services.spoonacular import get_recipe as _get_recipe_from_meal_plan
except (ImportError, ModuleNotFoundError):
    _get_recipe_from_meal_plan = None


BASE_URL = "https://api.spoonacular.com"


def _fallback_get(path, params):
    """Call Spoonacular with our key; return JSON or None on failure."""
    api_key = os.environ.get("SPOONACULAR_API_KEY", "")
    if not api_key:
        return None
    params = {**params, "apiKey": api_key}
    try:
        response = requests.get(BASE_URL + path, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def get_recipe(recipe_id):
    """
    Full recipe with nutrition, cached for 1 hour (Spoonacular's limit).
    Uses meal_plan's service if available, otherwise runs the identical cached implementation.
    """
    if _get_recipe_from_meal_plan is not None:
        return _get_recipe_from_meal_plan(recipe_id)

    key = f"spoon:recipe:{recipe_id}"
    recipe = cache.get(key)
    if recipe is None:
        recipe = _fallback_get(f"/recipes/{recipe_id}/information", {"includeNutrition": "true"})
        if recipe:
            cache.set(key, recipe, 60 * 60)
    return recipe


# Nutrient names / keywords to skip when calculating "Did you know?" vitamins & minerals
EXCLUDED_NUTRIENTS = {
    'calories',
    'fat',
    'saturated fat',
    'trans fat',
    'unsaturated fat',
    'carbohydrates',
    'net carbohydrates',
    'sugar',
    'sodium',
    'cholesterol',
    'protein',
}


def extract_calories(recipe):
    """Extract calorie count as integer or string from recipe nutrition nutrients."""
    if not recipe or 'nutrition' not in recipe:
        return None
    nutrients = recipe['nutrition'].get('nutrients', [])
    for nutrient in nutrients:
        if nutrient.get('name', '').strip().lower() == 'calories':
            amount = nutrient.get('amount')
            if amount is not None:
                return round(amount)
    return None


def get_did_you_know(recipe):
    """
    From nutrition.nutrients, pick the two vitamins or minerals with the highest percentOfDailyNeeds.
    Skip calories, fat, carbohydrates, sugar, sodium, and cholesterol.
    Write each one as: "One serving gives you <percent>% of your daily <nutrient>."
    If nothing qualifies, return an empty list.
    """
    if not recipe or 'nutrition' not in recipe:
        return []

    nutrients = recipe['nutrition'].get('nutrients', [])
    candidates = []

    for item in nutrients:
        name = item.get('name', '').strip()
        name_lower = name.lower()

        # Skip excluded macronutrients
        if name_lower in EXCLUDED_NUTRIENTS:
            continue

        percent = item.get('percentOfDailyNeeds')
        if percent is not None and percent > 0:
            candidates.append({
                'name': name,
                'percent': percent,
            })

    # Sort descending by percent of daily needs
    candidates.sort(key=lambda x: x['percent'], reverse=True)

    top_two = candidates[:2]
    facts = []
    for item in top_two:
        rounded_percent = round(item['percent'])
        facts.append(f"One serving gives you {rounded_percent}% of your daily {item['name']}.")

    return facts


def extract_ingredients(recipe):
    """Extract list of original ingredient strings from extendedIngredients."""
    if not recipe:
        return []
    ingredients = []
    for item in recipe.get('extendedIngredients', []):
        text = item.get('original') or item.get('originalString') or item.get('name')
        if text:
            ingredients.append(text)
    return ingredients


def extract_instructions(recipe):
    """Extract ordered step strings from analyzedInstructions."""
    if not recipe:
        return []
    steps = []
    analyzed = recipe.get('analyzedInstructions', [])
    for instruction_block in analyzed:
        for step_obj in instruction_block.get('steps', []):
            step_text = step_obj.get('step', '').strip()
            if step_text:
                steps.append(step_text)
    return steps
