import os
from urllib.parse import urlparse
import requests
from django.core.cache import cache

try:
    from meal_plan.services.spoonacular import get_recipe as _get_recipe_from_meal_plan
except (ImportError, ModuleNotFoundError):
    _get_recipe_from_meal_plan = None


BASE_URL = "https://api.spoonacular.com"


def is_safe_external_url(url):
    """
    Validate that an external URL only uses http or https schemes.
    Prevents XSS via javascript: or data: pseudo-protocols.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False


def _fallback_get(path, params):
    """
    Call Spoonacular with our key; return JSON or None on failure.
    Safely catches both network errors and invalid JSON decode errors.
    """
    api_key = os.environ.get("SPOONACULAR_API_KEY", "")
    if not api_key:
        return None
    params = {**params, "apiKey": api_key}
    try:
        response = requests.get(BASE_URL + path, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError, KeyError):
        return None


def get_recipe(recipe_id):
    """
    Full recipe with nutrition, cached for 1 hour (Spoonacular's limit).
    Validates recipe_id as a positive integer to prevent path traversal or SSRF.
    """
    try:
        recipe_id = int(recipe_id)
        if recipe_id <= 0:
            return None
    except (ValueError, TypeError):
        return None

    if _get_recipe_from_meal_plan is not None:
        return _get_recipe_from_meal_plan(recipe_id)

    key = f"spoon:recipe:{recipe_id}"
    recipe = cache.get(key)
    if recipe is None:
        recipe = _fallback_get(f"/recipes/{recipe_id}/information", {"includeNutrition": "true"})
        if recipe and isinstance(recipe, dict):
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
    """Safely extract calorie count as integer from recipe nutrition nutrients."""
    if not recipe or not isinstance(recipe, dict) or 'nutrition' not in recipe:
        return None
    nutrition = recipe.get('nutrition')
    if not isinstance(nutrition, dict):
        return None
    nutrients = nutrition.get('nutrients', [])
    if not isinstance(nutrients, list):
        return None

    for nutrient in nutrients:
        if not isinstance(nutrient, dict):
            continue
        if nutrient.get('name', '').strip().lower() == 'calories':
            amount = nutrient.get('amount')
            if amount is not None:
                try:
                    return round(float(amount))
                except (ValueError, TypeError):
                    return None
    return None


def get_did_you_know(recipe):
    """
    From nutrition.nutrients, pick the two vitamins or minerals with the highest percentOfDailyNeeds.
    Skip calories, fat, carbohydrates, sugar, sodium, and cholesterol.
    Write each one as: "One serving gives you <percent>% of your daily <nutrient>."
    If nothing qualifies, return an empty list.
    """
    if not recipe or not isinstance(recipe, dict) or 'nutrition' not in recipe:
        return []

    nutrition = recipe.get('nutrition')
    if not isinstance(nutrition, dict):
        return []
    nutrients = nutrition.get('nutrients', [])
    if not isinstance(nutrients, list):
        return []

    candidates = []

    for item in nutrients:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name', '')).strip()
        name_lower = name.lower()

        # Skip excluded macronutrients
        if name_lower in EXCLUDED_NUTRIENTS:
            continue

        percent_raw = item.get('percentOfDailyNeeds')
        if percent_raw is not None:
            try:
                percent = float(percent_raw)
                if percent > 0:
                    candidates.append({
                        'name': name,
                        'percent': percent,
                    })
            except (ValueError, TypeError):
                continue

    # Sort descending by percent of daily needs
    candidates.sort(key=lambda x: x['percent'], reverse=True)

    top_two = candidates[:2]
    facts = []
    for item in top_two:
        rounded_percent = round(item['percent'])
        facts.append(f"One serving gives you {rounded_percent}% of your daily {item['name']}.")

    return facts


def extract_ingredients(recipe):
    """Extract list of original ingredient strings from extendedIngredients with type safety."""
    if not recipe or not isinstance(recipe, dict):
        return []
    raw_ingredients = recipe.get('extendedIngredients', [])
    if not isinstance(raw_ingredients, list):
        return []

    ingredients = []
    for item in raw_ingredients:
        if isinstance(item, dict):
            text = item.get('original') or item.get('originalString') or item.get('name')
            if text and isinstance(text, str):
                cleaned = text.strip()
                if cleaned:
                    ingredients.append(cleaned)
    return ingredients


def extract_instructions(recipe):
    """Extract ordered step strings from analyzedInstructions with type safety."""
    if not recipe or not isinstance(recipe, dict):
        return []
    analyzed = recipe.get('analyzedInstructions', [])
    if not isinstance(analyzed, list):
        return []

    steps = []
    for instruction_block in analyzed:
        if not isinstance(instruction_block, dict):
            continue
        raw_steps = instruction_block.get('steps', [])
        if not isinstance(raw_steps, list):
            continue
        for step_obj in raw_steps:
            if isinstance(step_obj, dict):
                step_text = step_obj.get('step', '')
                if step_text and isinstance(step_text, str):
                    cleaned = step_text.strip()
                    if cleaned:
                        steps.append(cleaned)
    return steps
