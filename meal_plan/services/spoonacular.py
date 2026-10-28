import hashlib
import json
import logging
import os

import requests
from django.conf import settings
from django.core.cache import cache

BASE_URL = 'https://api.spoonacular.com'
IMAGE_URL = 'https://img.spoonacular.com/recipes/{recipe_id}-556x370.{image_type}'
IMAGE_TYPES = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
TIMEOUT_SECONDS = 10
CACHE_SECONDS = 60 * 60
BULK_LIMIT = 100

logger = logging.getLogger(__name__)

MESSAGES = {
    'missing_key': 'Recipe data is not available right now.',
    'quota': "Spoonacular's daily limit has been reached, so recipe data is not available right now. Please try again tomorrow.",
    'unauthorized': 'Recipe data is not available right now.',
    'unavailable': 'Recipe data is not available right now. Please try again in a moment.',
}

DEBUG_MESSAGES = {
    'missing_key': 'Recipe data is not available because SPOONACULAR_API_KEY is missing from your .env file.',
    'unauthorized': 'Spoonacular did not accept the key in your .env file. Check SPOONACULAR_API_KEY.',
}


class SpoonacularError(Exception):
    def __init__(self, reason='unavailable'):
        super().__init__(reason)
        self.reason = reason

    @property
    def message(self):
        if settings.DEBUG and self.reason in DEBUG_MESSAGES:
            return DEBUG_MESSAGES[self.reason]
        return MESSAGES.get(self.reason, MESSAGES['unavailable'])


def _request(path, params):
    api_key = os.environ.get('SPOONACULAR_API_KEY', '').strip()
    if not api_key:
        logger.warning('SPOONACULAR_API_KEY is not set, so %s was not called.', path)
        raise SpoonacularError('missing_key')
    try:
        response = requests.get(
            BASE_URL + path,
            params=params,
            headers={'x-api-key': api_key},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        logger.warning('Spoonacular %s failed (%s).', path, type(error).__name__)
        raise SpoonacularError('unavailable') from None
    if response.status_code != 200:
        logger.warning('Spoonacular %s answered HTTP %s.', path, response.status_code)
        if response.status_code == 402:
            raise SpoonacularError('quota')
        if response.status_code in (401, 403):
            raise SpoonacularError('unauthorized')
        raise SpoonacularError('unavailable')
    try:
        return response.json()
    except ValueError:
        logger.warning('Spoonacular %s did not answer with JSON.', path)
        raise SpoonacularError('unavailable') from None


def _get(path, params):
    try:
        return _request(path, params)
    except SpoonacularError:
        return None


def _positive_int(value):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def is_recipe(data):
    return isinstance(data, dict) and _positive_int(data.get('id')) is not None


def _recipe_key(recipe_id):
    return f'spoon:recipe:{recipe_id}'


def _cache_key(prefix, params, cache_variant):
    payload = json.dumps({'params': params, 'variant': str(cache_variant)}, sort_keys=True, default=str)
    return f'spoon:{prefix}:{hashlib.sha1(payload.encode()).hexdigest()}'


def _cached(prefix, path, params, cache_variant=''):
    key = _cache_key(prefix, params, cache_variant)
    data = cache.get(key)
    if data is None:
        data = _request(path, params)
        cache.set(key, data, CACHE_SECONDS)
    return data


def _clean_params(params):
    clean = {}
    for name, value in params.items():
        if value is None or value == '' or value == [] or value == ():
            continue
        if isinstance(value, bool):
            value = 'true' if value else 'false'
        elif isinstance(value, (list, tuple)):
            value = ','.join(str(item) for item in value)
        clean[name] = value
    return clean


def get_recipe(recipe_id):
    recipe_id = _positive_int(recipe_id)
    if recipe_id is None:
        return None
    key = _recipe_key(recipe_id)
    recipe = cache.get(key)
    if recipe is None:
        recipe = _get(f'/recipes/{recipe_id}/information', {'includeNutrition': 'true'})
        if not is_recipe(recipe):
            return None
        cache.set(key, recipe, CACHE_SECONDS)
    return recipe


def get_cached_recipe(recipe_id):
    recipe_id = _positive_int(recipe_id)
    if recipe_id is None:
        return None
    return cache.get(_recipe_key(recipe_id))


def get_recipes(recipe_ids):
    ids = []
    for value in recipe_ids:
        recipe_id = _positive_int(value)
        if recipe_id is not None and recipe_id not in ids:
            ids.append(recipe_id)
    recipes = {}
    missing = []
    for recipe_id in ids:
        cached = cache.get(_recipe_key(recipe_id))
        if cached is None:
            missing.append(recipe_id)
        else:
            recipes[recipe_id] = cached
    for start in range(0, len(missing), BULK_LIMIT):
        chunk = missing[start:start + BULK_LIMIT]
        try:
            data = _request('/recipes/informationBulk', {
                'ids': ','.join(str(recipe_id) for recipe_id in chunk),
                'includeNutrition': 'true',
            })
        except SpoonacularError as error:
            return recipes, error
        if not isinstance(data, list):
            return recipes, SpoonacularError('unavailable')
        for recipe in data:
            if is_recipe(recipe) and recipe['id'] in chunk:
                recipes[recipe['id']] = recipe
                cache.set(_recipe_key(recipe['id']), recipe, CACHE_SECONDS)
    return recipes, None


def generate_meal_plan(time_frame, target_calories, diet='', exclude=(), cache_variant=0):
    params = _clean_params({
        'timeFrame': time_frame,
        'targetCalories': int(target_calories),
        'diet': diet,
        'exclude': list(exclude),
    })
    return _cached('plan', '/mealplanner/generate', params, cache_variant)


def search_recipes(params, cache_variant=''):
    data = _cached('search', '/recipes/complexSearch', _clean_params(params), cache_variant)
    if not isinstance(data, dict):
        raise SpoonacularError('unavailable')
    return data


def image_url(recipe_id, image_type='jpg'):
    recipe_id = _positive_int(recipe_id)
    if recipe_id is None:
        return ''
    image_type = str(image_type or 'jpg').lower().lstrip('.')
    if image_type not in IMAGE_TYPES:
        image_type = 'jpg'
    return IMAGE_URL.format(recipe_id=recipe_id, image_type=image_type)
