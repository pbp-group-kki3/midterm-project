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


# Micronutrients recognized as valid vitamins or minerals per guidelines
VALID_VITAMINS_AND_MINERALS = {
    'vitamin a',
    'vitamin b1',
    'thiamin',
    'vitamin b2',
    'riboflavin',
    'vitamin b3',
    'niacin',
    'vitamin b5',
    'pantothenic acid',
    'vitamin b6',
    'vitamin b12',
    'vitamin c',
    'vitamin d',
    'vitamin e',
    'vitamin k',
    'folate',
    'folic acid',
    'choline',
    'calcium',
    'iron',
    'zinc',
    'magnesium',
    'potassium',
    'phosphorus',
    'copper',
    'manganese',
    'selenium',
    'iodine',
}

# Non-vitamin/mineral nutrients to strictly exclude from "Did you know?"
EXCLUDED_NUTRIENTS = {
    'alcohol',
    'caffeine',
    'calories',
    'fat',
    'saturated fat',
    'trans fat',
    'unsaturated fat',
    'monounsaturated fat',
    'polyunsaturated fat',
    'carbohydrates',
    'net carbohydrates',
    'sugar',
    'sodium',
    'cholesterol',
    'protein',
    'fiber',
}


def is_valid_vitamin_or_mineral(name):
    """Verify that a nutrient is a genuine vitamin or mineral, not alcohol, fat, or macro."""
    if not name or not isinstance(name, str):
        return False
    clean = name.lower().replace('%', '').strip()
    if clean in EXCLUDED_NUTRIENTS:
        return False
    return clean.startswith('vitamin') or clean in VALID_VITAMINS_AND_MINERALS


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


def extract_key_nutrients(recipe):
    """
    Extract key per-serving macronutrients matching Figma wireframe:
    Calories, Protein, Fat, Carbohydrates.
    """
    if not recipe or not isinstance(recipe, dict) or 'nutrition' not in recipe:
        return []
    nutrition = recipe.get('nutrition')
    if not isinstance(nutrition, dict):
        return []
    nutrients = nutrition.get('nutrients', [])
    if not isinstance(nutrients, list):
        return []

    target_order = ['calories', 'protein', 'fat', 'carbohydrates']
    found = {}

    for item in nutrients:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name', '')).strip()
        lower = name.lower()
        if lower in target_order and lower not in found:
            amount = item.get('amount')
            unit = item.get('unit', '')
            if amount is not None:
                try:
                    amount_val = float(amount)
                    if lower == 'calories':
                        display_amount = f"{amount_val:.1f} {unit}"
                    else:
                        display_amount = f"{round(amount_val)} {unit}" if amount_val.is_integer() else f"{amount_val:.1f} {unit}"
                    found[lower] = {
                        'name': name.capitalize(),
                        'display': display_amount,
                    }
                except (ValueError, TypeError):
                    continue

    result = []
    for key in target_order:
        if key in found:
            result.append(found[key])
    return result


def get_did_you_know(recipe):
    """
    From nutrition.nutrients, pick the two vitamins or minerals with the highest percentOfDailyNeeds.
    Skip calories, fat, carbohydrates, sugar, sodium, cholesterol, alcohol, etc.
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
    seen_nutrients = set()

    for item in nutrients:
        if not isinstance(item, dict):
            continue
        raw_name = str(item.get('name', '')).strip()
        # Clean out any trailing % from raw nutrient names like "Alcohol %"
        clean_name = raw_name.replace('%', '').strip()
        name_lower = clean_name.lower()

        # Strict validation: must be a genuine vitamin or mineral
        if not is_valid_vitamin_or_mineral(clean_name):
            continue

        # Prevent duplicate entries for the same nutrient
        if name_lower in seen_nutrients:
            continue

        percent_raw = item.get('percentOfDailyNeeds')
        if percent_raw is not None:
            try:
                percent = float(percent_raw)
                if percent > 0:
                    seen_nutrients.add(name_lower)
                    candidates.append({
                        'name': clean_name,
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


def build_recipe_snapshot(recipe):
    """
    Serializes a recipe dict into a standalone, portable snapshot.
    Preserves exact recipe details at bookmark time, immune to Spoonacular
    rate limits, downtime, or future modifications.
    """
    if not recipe or not isinstance(recipe, dict):
        return {}

    raw_source_url = recipe.get('sourceUrl')
    source_url = raw_source_url if is_safe_external_url(raw_source_url) else 'https://spoonacular.com'

    raw_image_url = recipe.get('image')
    safe_image_url = raw_image_url if is_safe_external_url(raw_image_url) else None

    dish_types = recipe.get('dishTypes', [])
    if not isinstance(dish_types, list):
        dish_types = []

    ingredients = extract_ingredients(recipe)
    instructions = extract_instructions(recipe)
    calories = extract_calories(recipe)
    key_nutrients = extract_key_nutrients(recipe)
    did_you_know = get_did_you_know(recipe)

    return {
        'id': recipe.get('id'),
        'title': str(recipe.get('title') or '').strip(),
        'image': safe_image_url,
        'readyInMinutes': recipe.get('readyInMinutes'),
        'ready_in_minutes': recipe.get('readyInMinutes'),
        'servings': recipe.get('servings'),
        'healthScore': recipe.get('healthScore'),
        'health_score': recipe.get('healthScore'),
        'dishTypes': dish_types,
        'dish_types': dish_types,
        'calories': calories,
        'key_nutrients': key_nutrients,
        'did_you_know': did_you_know,
        'ingredients': ingredients,
        'instructions': instructions,
        'extendedIngredients': [{'original': item} for item in ingredients],
        'analyzedInstructions': [{'steps': [{'step': step} for step in instructions]}],
        'sourceName': str(recipe.get('sourceName') or 'Spoonacular')[:100],
        'source_name': str(recipe.get('sourceName') or 'Spoonacular')[:100],
        'sourceUrl': source_url,
        'source_url': source_url,
    }
