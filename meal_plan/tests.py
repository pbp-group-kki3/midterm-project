import os
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from meal_plan.models import MealPlan, MealPlanEntry
from meal_plan.services import planner, spoonacular
from meal_plan.services.spoonacular import SpoonacularError

TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'meal-plan-tests',
    },
}

INVALID_JSON = object()


def make_recipe(recipe_id, title, kcal=400, protein=20.0, carbs=40.0, fat=10.0, **extra):
    recipe = {
        'id': recipe_id,
        'title': title,
        'image': f'https://img.spoonacular.com/recipes/{recipe_id}-312x231.jpg',
        'imageType': 'jpg',
        'readyInMinutes': 30,
        'servings': 2,
        'sourceName': 'Test Kitchen',
        'sourceUrl': f'https://example.com/recipes/{recipe_id}',
        'vegetarian': False,
        'vegan': False,
        'glutenFree': False,
        'dairyFree': False,
        'diets': [],
        'extendedIngredients': [{'original': '1 cup oats'}],
        'analyzedInstructions': [],
        'nutrition': {
            'nutrients': [
                {'name': 'Calories', 'amount': kcal, 'unit': 'kcal'},
                {'name': 'Fat', 'amount': fat, 'unit': 'g'},
                {'name': 'Carbohydrates', 'amount': carbs, 'unit': 'g'},
                {'name': 'Protein', 'amount': protein, 'unit': 'g'},
            ],
        },
    }
    recipe.update(extra)
    return recipe


def plan_meal(recipe):
    return {key: recipe[key] for key in ('id', 'imageType', 'title', 'readyInMinutes', 'servings', 'sourceUrl')}


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data

    def json(self):
        if self._data is INVALID_JSON:
            raise ValueError('not json')
        return self._data


class FakeSpoonacular:
    def __init__(self):
        self.recipes = {}
        self.calls = []
        self.failures = {}
        self.breakfasts = []
        self.mains = []
        self.search_results = []
        self.total_results = None
        self.short_day = False

    def add(self, *recipes):
        for recipe in recipes:
            self.recipes[recipe['id']] = recipe
        return recipes

    def paths(self):
        return [call.path for call in self.calls]

    def calls_to(self, path):
        return [call for call in self.calls if call.path == path]

    def _day(self, number):
        breakfast = self.breakfasts[number % len(self.breakfasts)]
        lunch = self.mains[(2 * number) % len(self.mains)]
        dinner = self.mains[(2 * number + 1) % len(self.mains)]
        meals = [plan_meal(breakfast), plan_meal(lunch), plan_meal(dinner)]
        if self.short_day:
            meals = meals[:2]
        return {'meals': meals, 'nutrients': {'calories': 1800.0, 'protein': 80.0, 'fat': 60.0, 'carbohydrates': 220.0}}

    def __call__(self, url, params=None, headers=None, timeout=None):
        path = url.replace(spoonacular.BASE_URL, '')
        params = dict(params or {})
        self.calls.append(SimpleNamespace(url=url, path=path, params=params, headers=dict(headers or {}), timeout=timeout))
        for prefix, failure in self.failures.items():
            if path.startswith(prefix):
                if isinstance(failure, Exception):
                    raise failure
                if failure is INVALID_JSON:
                    return FakeResponse(200, INVALID_JSON)
                return FakeResponse(failure, {'status': 'failure', 'code': failure})
        if path == '/mealplanner/generate':
            if params.get('timeFrame') == 'day':
                return FakeResponse(200, self._day(0))
            names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            return FakeResponse(200, {'week': {name: self._day(index) for index, name in enumerate(names)}})
        if path == '/recipes/informationBulk':
            ids = [int(value) for value in params.get('ids', '').split(',') if value]
            return FakeResponse(200, [self.recipes[recipe_id] for recipe_id in ids if recipe_id in self.recipes])
        if path == '/recipes/complexSearch':
            offset = int(params.get('offset', 0))
            number = int(params.get('number', 10))
            results = self.search_results[offset:offset + number]
            total = self.total_results if self.total_results is not None else len(self.search_results)
            return FakeResponse(200, {'results': results, 'offset': offset, 'number': number, 'totalResults': total})
        if path.startswith('/recipes/') and path.endswith('/information'):
            recipe_id = int(path.split('/')[2])
            if recipe_id in self.recipes:
                return FakeResponse(200, self.recipes[recipe_id])
            return FakeResponse(404, {'status': 'failure', 'code': 404})
        return FakeResponse(404, {'status': 'failure'})


@override_settings(
    ROOT_URLCONF='meal_plan.test_urls',
    CACHES=TEST_CACHES,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class MealPlanTestCase(TestCase):
    password = 'a-long-test-password'

    def setUp(self):
        cache.clear()
        self.api = FakeSpoonacular()
        self.api.breakfasts = list(self.api.add(
            make_recipe(101, 'Overnight Oats', kcal=310, protein=11, carbs=52, fat=7, vegetarian=True),
            make_recipe(102, 'Spinach Omelette', kcal=205, protein=16, carbs=3.1, fat=14.2, vegetarian=True, glutenFree=True),
        ))
        self.api.mains = list(self.api.add(
            make_recipe(201, 'Chickpea Bruschetta', kcal=320, protein=11, carbs=42.1, fat=9.3, vegan=True, vegetarian=True, dairyFree=True),
            make_recipe(202, 'Mango Fried Rice', kcal=486, protein=16, carbs=95.4, fat=4, vegan=True, vegetarian=True),
            make_recipe(203, 'Lentil Soup', kcal=290, protein=17, carbs=41, fat=5, vegan=True, vegetarian=True, glutenFree=True),
            make_recipe(204, 'Tofu Stir-Fry', kcal=410, protein=24, carbs=38, fat=18, vegan=True, vegetarian=True),
        ))
        self.snacks = list(self.api.add(
            make_recipe(301, 'Apple Oat Bars', kcal=180, protein=3, carbs=30, fat=5),
            make_recipe(302, 'Mango Lassi', kcal=150, protein=5, carbs=28, fat=2.5),
            make_recipe(303, 'Roasted Chickpeas', kcal=220, protein=8, carbs=20, fat=9),
        ))
        get_patcher = patch.object(spoonacular.requests, 'get', side_effect=self.api)
        self.requests_get = get_patcher.start()
        self.addCleanup(get_patcher.stop)
        env_patcher = patch.dict(os.environ, {'SPOONACULAR_API_KEY': 'test-key'})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        self.user = User.objects.create_user('reyhan', 'reyhan@example.com', self.password)
        self.other = User.objects.create_user('other', 'other@example.com', self.password)

    def login(self, user=None):
        self.client.force_login(user or self.user)

    def set_profile(self, user=None, **values):
        profile = (user or self.user).profile
        for name, value in values.items():
            setattr(profile, name, value)
        profile.save()

    def make_plan(self, user=None, days=2, diet='none', allergies=None, include_snack=False, name='Green week'):
        plan = MealPlan.objects.create(
            user=user or self.user,
            name=name,
            date=date(2026, 10, 26),
            timeframe='day' if days == 1 else 'week',
            days=days,
            diet=diet,
            allergies=allergies or [],
            include_snack=include_snack,
            calorie_goal=1800,
        )
        recipe_ids = [101, 201, 202, 102, 203, 204]
        for day in range(1, days + 1):
            for index, slot in enumerate(['breakfast', 'lunch', 'dinner']):
                MealPlanEntry.objects.create(plan=plan, day=day, slot=slot, recipe_id=recipe_ids[((day - 1) * 3 + index) % len(recipe_ids)])
            if include_snack:
                MealPlanEntry.objects.create(plan=plan, day=day, slot='snack', recipe_id=301)
        return plan


class SpoonacularClientTests(MealPlanTestCase):
    def test_get_recipe_calls_the_information_endpoint_once_and_caches_it(self):
        with patch.object(cache, 'set', wraps=cache.set) as cache_set:
            recipe = spoonacular.get_recipe(101)
            again = spoonacular.get_recipe('101')
        self.assertEqual(recipe['title'], 'Overnight Oats')
        self.assertEqual(again, recipe)
        self.assertEqual(self.api.paths(), ['/recipes/101/information'])
        self.assertEqual(self.api.calls[0].params, {'includeNutrition': 'true'})
        cache_set.assert_called_once_with('spoon:recipe:101', recipe, 60 * 60)

    def test_get_recipe_sends_the_key_in_a_header_with_a_timeout(self):
        spoonacular.get_recipe(101)
        call = self.api.calls[0]
        self.assertEqual(call.headers, {'x-api-key': 'test-key'})
        self.assertNotIn('apiKey', call.params)
        self.assertNotIn('test-key', call.url)
        self.assertEqual(call.timeout, 10)

    def test_get_recipe_returns_none_for_bad_ids_without_calling_the_api(self):
        for value in (0, -3, 'abc', None, True):
            self.assertIsNone(spoonacular.get_recipe(value))
        self.assertEqual(self.api.calls, [])

    def test_get_recipe_returns_none_and_caches_nothing_when_the_api_fails(self):
        cases = [402, 401, 500, requests.Timeout(), requests.ConnectionError(), INVALID_JSON]
        for failure in cases:
            with self.subTest(failure=failure):
                cache.clear()
                self.api.failures = {'/recipes/101': failure}
                with self.assertLogs('meal_plan.services.spoonacular', 'WARNING'):
                    self.assertIsNone(spoonacular.get_recipe(101))
                self.assertIsNone(cache.get('spoon:recipe:101'))

    def test_missing_key_never_calls_the_api(self):
        with patch.dict(os.environ, {'SPOONACULAR_API_KEY': ''}):
            with self.assertLogs('meal_plan.services.spoonacular', 'WARNING'):
                self.assertIsNone(spoonacular.get_recipe(101))
            with self.assertLogs('meal_plan.services.spoonacular', 'WARNING'):
                with self.assertRaises(SpoonacularError) as raised:
                    spoonacular.search_recipes({'query': 'oats'})
        self.assertEqual(raised.exception.reason, 'missing_key')
        self.assertEqual(self.api.calls, [])

    def test_errors_carry_a_friendly_message(self):
        self.api.failures = {'/recipes/complexSearch': 402}
        with self.assertLogs('meal_plan.services.spoonacular', 'WARNING'):
            with self.assertRaises(SpoonacularError) as raised:
                spoonacular.search_recipes({'query': 'oats'})
        self.assertEqual(raised.exception.reason, 'quota')
        self.assertIn('daily limit', raised.exception.message)

    def test_debug_message_explains_a_missing_key(self):
        error = SpoonacularError('missing_key')
        with self.settings(DEBUG=True):
            self.assertIn('SPOONACULAR_API_KEY', error.message)
        with self.settings(DEBUG=False):
            self.assertNotIn('SPOONACULAR_API_KEY', error.message)

    def test_get_helper_returns_json_or_none(self):
        self.assertEqual(spoonacular._get('/recipes/101/information', {})['id'], 101)
        self.api.failures = {'/recipes/101': 500}
        with self.assertLogs('meal_plan.services.spoonacular', 'WARNING'):
            self.assertIsNone(spoonacular._get('/recipes/101/information', {}))

    def test_get_recipes_fetches_only_missing_ids_in_one_bulk_call(self):
        spoonacular.get_recipe(101)
        recipes, error = spoonacular.get_recipes([101, 201, 202, 201, 'x'])
        self.assertIsNone(error)
        self.assertEqual(set(recipes), {101, 201, 202})
        bulk = self.api.calls_to('/recipes/informationBulk')
        self.assertEqual(len(bulk), 1)
        self.assertEqual(bulk[0].params, {'ids': '201,202', 'includeNutrition': 'true'})
        self.assertIsNotNone(cache.get('spoon:recipe:202'))
        spoonacular.get_recipes([201, 202])
        self.assertEqual(len(self.api.calls_to('/recipes/informationBulk')), 1)

    def test_get_recipes_keeps_cached_recipes_when_the_bulk_call_fails(self):
        spoonacular.get_recipe(101)
        self.api.failures = {'/recipes/informationBulk': 402}
        with self.assertLogs('meal_plan.services.spoonacular', 'WARNING'):
            recipes, error = spoonacular.get_recipes([101, 201])
        self.assertEqual(set(recipes), {101})
        self.assertEqual(error.reason, 'quota')

    def test_generate_meal_plan_is_cached_per_variant(self):
        first = spoonacular.generate_meal_plan('week', 1800, 'vegetarian', ['peanut', 'pork'], 'a')
        spoonacular.generate_meal_plan('week', 1800, 'vegetarian', ['peanut', 'pork'], 'a')
        spoonacular.generate_meal_plan('week', 1800, 'vegetarian', ['peanut', 'pork'], 'b')
        calls = self.api.calls_to('/mealplanner/generate')
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].params, {'timeFrame': 'week', 'targetCalories': 1800, 'diet': 'vegetarian', 'exclude': 'peanut,pork'})
        self.assertIn('monday', first['week'])

    def test_search_recipes_cleans_parameters(self):
        spoonacular.search_recipes({
            'query': '',
            'type': 'breakfast',
            'diet': ['pescetarian', 'vegetarian'],
            'intolerances': [],
            'addRecipeNutrition': True,
            'maxCalories': None,
            'number': 3,
        })
        self.assertEqual(self.api.calls[0].params, {'type': 'breakfast', 'diet': 'pescetarian,vegetarian', 'addRecipeNutrition': 'true', 'number': 3})

    def test_image_url_uses_the_556x370_size(self):
        self.assertEqual(spoonacular.image_url(101, 'png'), 'https://img.spoonacular.com/recipes/101-556x370.png')
        self.assertEqual(spoonacular.image_url(101, 'exe'), 'https://img.spoonacular.com/recipes/101-556x370.jpg')
        self.assertEqual(spoonacular.image_url(-1, 'jpg'), '')

    def test_meal_of_the_day_can_import_get_recipe(self):
        from meal_plan.services.spoonacular import get_recipe

        self.assertEqual(get_recipe(201)['id'], 201)


class PlannerTests(MealPlanTestCase):
    def test_plan_filters_turn_choices_into_spoonacular_words(self):
        filters = planner.plan_filters('pescatarian', ['dairy', 'seafood', 'tree_nut'])
        self.assertEqual(filters['diet'], 'pescetarian')
        self.assertEqual(filters['intolerances'], ['dairy', 'seafood', 'shellfish', 'tree nut'])
        self.assertEqual(filters['exclude'], [])
        halal = planner.plan_filters('halal', [])
        self.assertEqual(halal['diet'], '')
        self.assertEqual(halal['exclude'], ['pork', 'bacon', 'ham', 'wine', 'beer'])

    def test_plan_filters_add_current_profile_preferences(self):
        prefs = {'diet': 'halal', 'spoonacular_intolerances': ['peanut', 'dairy']}
        filters = planner.plan_filters('vegan', ['dairy'], prefs)
        self.assertEqual(filters['diet'], 'vegan')
        self.assertEqual(filters['intolerances'], ['dairy', 'peanut'])
        self.assertEqual(filters['exclude'], ['pork', 'bacon', 'ham', 'wine', 'beer'])

    def test_profile_defaults_come_from_the_profile(self):
        self.set_profile(diet='halal', allergies=['Milk', 'Peanuts', 'Shellfish', 'Sesame'], calorie_target=1800, meals_per_day=4)
        defaults = planner.profile_defaults(self.user)
        self.assertEqual(defaults['diet'], 'halal')
        self.assertEqual(defaults['allergies'], ['dairy', 'peanut', 'seafood', 'sesame'])
        self.assertEqual(defaults['calorie_target'], 1800)
        self.assertTrue(defaults['include_snack'])

    def test_daily_goal_prefers_the_form_then_the_profile_then_2000(self):
        self.assertEqual(planner.daily_goal(2200, self.user), (2200, 'goal'))
        self.assertEqual(planner.daily_goal(None, self.user), (2000, 'default'))
        self.set_profile(calorie_target=1700)
        self.assertEqual(planner.daily_goal(None, self.user), (1700, 'profile'))
        self.set_profile(calorie_target=90000)
        self.assertEqual(planner.daily_goal(None, self.user), (2000, 'default'))

    def test_card_from_recipe_reads_nutrition_and_labels(self):
        card = planner.card_from_recipe(self.api.recipes[102])
        self.assertEqual(card['calories'], 205)
        self.assertEqual(card['meal_meta'], '30 min · 205 kcal')
        self.assertEqual(card['macros'], 'P 16.0 g · C 3.1 g · F 14.2 g')
        self.assertEqual(card['grid_meta'], '30 min · 2 servings')
        self.assertEqual(card['grid_nutrition'], '205 kcal · P 16 g')
        self.assertEqual(card['option_meta'], '30 min · 205 kcal · P 16 g')
        self.assertEqual(card['labels'], ['Vegetarian', 'Gluten free'])
        self.assertEqual(card['image_url'], 'https://img.spoonacular.com/recipes/102-556x370.jpg')
        self.assertTrue(card['complete'])

    def test_card_from_recipe_never_links_to_unsafe_urls(self):
        recipe = make_recipe(555, 'Odd Soup', sourceUrl='javascript:alert(1)', spoonacularSourceUrl='')
        card = planner.card_from_recipe(recipe)
        self.assertEqual(card['source_url'], 'https://spoonacular.com/recipes/odd-soup-555')

    def test_card_from_recipe_says_one_serving(self):
        card = planner.card_from_recipe(make_recipe(556, 'Toast', servings=1))
        self.assertEqual(card['grid_meta'], '30 min · 1 serving')

    def test_create_plan_for_one_day_uses_the_day_generator(self):
        plan = planner.create_plan(self.user, {
            'name': 'Monday', 'start_date': date(2026, 10, 26), 'days': 1, 'diet': 'vegetarian',
            'allergies': ['peanut'], 'include_snack': False, 'calorie_goal': None,
        })
        generate = self.api.calls_to('/mealplanner/generate')
        self.assertEqual(len(generate), 1)
        self.assertEqual(generate[0].params, {'timeFrame': 'day', 'targetCalories': 2000, 'diet': 'vegetarian', 'exclude': 'peanut'})
        self.assertEqual(plan.timeframe, 'day')
        self.assertEqual(plan.calorie_goal, 2000)
        self.assertEqual(list(plan.entries.values_list('day', 'slot', 'recipe_id')), [(1, 'breakfast', 101), (1, 'lunch', 201), (1, 'dinner', 202)])

    def test_create_plan_for_a_week_with_snacks(self):
        self.api.search_results = self.snacks
        plan = planner.create_plan(self.user, {
            'name': 'Green week', 'start_date': date(2026, 10, 26), 'days': 7, 'diet': 'halal',
            'allergies': ['gluten', 'seafood'], 'include_snack': True, 'calorie_goal': 1800,
        })
        generate = self.api.calls_to('/mealplanner/generate')
        self.assertEqual(len(generate), 1)
        self.assertEqual(generate[0].params, {
            'timeFrame': 'week',
            'targetCalories': 1620,
            'exclude': 'gluten,seafood,shellfish,pork,bacon,ham,wine,beer',
        })
        search = self.api.calls_to('/recipes/complexSearch')[0].params
        self.assertEqual(search['type'], 'snack')
        self.assertEqual(search['sort'], 'random')
        self.assertEqual(search['intolerances'], 'gluten,seafood,shellfish')
        self.assertEqual(search['excludeIngredients'], 'pork,bacon,ham,wine,beer')
        self.assertEqual(search['addRecipeInformation'], 'true')
        self.assertEqual(plan.entries.count(), 28)
        self.assertEqual(plan.entries.filter(slot='snack').count(), 7)
        self.assertTrue(plan.include_snack)
        self.assertEqual(plan.entries.filter(slot='snack', day=1).get().recipe_id, 301)

    def test_create_plan_for_fourteen_days_generates_two_weeks(self):
        plan = planner.create_plan(self.user, {
            'name': 'Long', 'start_date': date(2026, 10, 26), 'days': 14, 'diet': 'none',
            'allergies': [], 'include_snack': False, 'calorie_goal': 2100,
        })
        self.assertEqual(len(self.api.calls_to('/mealplanner/generate')), 2)
        self.assertEqual(plan.entries.count(), 42)
        self.assertEqual(plan.entries.filter(day=14).count(), 3)

    def test_create_plan_stops_when_spoonacular_cannot_fill_a_day(self):
        self.api.short_day = True
        with self.assertRaises(planner.PlanError):
            planner.create_plan(self.user, {
                'name': 'Strict', 'start_date': date(2026, 10, 26), 'days': 3, 'diet': 'vegan',
                'allergies': ['gluten', 'soy'], 'include_snack': False, 'calorie_goal': None,
            })
        self.assertFalse(MealPlan.objects.exists())

    def test_create_plan_without_snacks_when_the_snack_search_fails(self):
        self.api.failures = {'/recipes/complexSearch': 500}
        with self.assertLogs('meal_plan.services.spoonacular', 'WARNING'):
            plan = planner.create_plan(self.user, {
                'name': 'No snacks', 'start_date': date(2026, 10, 26), 'days': 2, 'diet': 'none',
                'allergies': [], 'include_snack': True, 'calorie_goal': None,
            })
        self.assertFalse(plan.include_snack)
        self.assertEqual(plan.entries.count(), 6)

    def test_plan_days_adds_up_calories_per_day(self):
        plan = self.make_plan(days=2)
        days, error = planner.plan_days(plan)
        self.assertIsNone(error)
        self.assertEqual(len(days), 2)
        self.assertEqual([meal['entry'].slot for meal in days[0]['meals']], ['breakfast', 'lunch', 'dinner'])
        self.assertEqual(days[0]['calories'], 310 + 320 + 486)
        self.assertEqual(days[0]['calories_label'], '1,116 kcal')
        self.assertEqual(len(self.api.calls_to('/recipes/informationBulk')), 1)

    def test_plan_days_still_works_when_details_are_unavailable(self):
        plan = self.make_plan(days=1)
        self.api.failures = {'/recipes/informationBulk': 402}
        with self.assertLogs('meal_plan.services.spoonacular', 'WARNING'):
            days, error = planner.plan_days(plan)
        self.assertEqual(error.reason, 'quota')
        self.assertFalse(days[0]['meals'][0]['recipe']['available'])
        self.assertIsNone(days[0]['calories'])

    def test_replacement_options_are_close_in_calories_and_skip_the_current_meal(self):
        plan = self.make_plan(days=1)
        entry = plan.entries.get(slot='breakfast')
        self.api.search_results = [
            make_recipe(101, 'Overnight Oats', kcal=310),
            make_recipe(401, 'Huge Breakfast', kcal=900),
            make_recipe(402, 'Yogurt Parfait', kcal=300),
            make_recipe(403, 'Avocado Toast', kcal=330),
            make_recipe(201, 'Chickpea Bruschetta', kcal=315),
            make_recipe(404, 'Tiny Breakfast', kcal=100),
        ]
        current, options = planner.replacement_options(plan, entry)
        self.assertEqual(current['id'], 101)
        self.assertEqual([option['id'] for option in options], [402, 403, 404])
        params = self.api.calls_to('/recipes/complexSearch')[0].params
        self.assertEqual(params['type'], 'breakfast')
        self.assertEqual(params['sort'], 'random')
        self.assertEqual(params['number'], 6)

    def test_replacement_options_use_main_course_for_lunch_and_profile_allergies(self):
        self.set_profile(allergies=['Peanuts'])
        plan = self.make_plan(days=1, diet='vegetarian', allergies=['gluten'])
        entry = plan.entries.get(slot='lunch')
        self.api.search_results = [make_recipe(410, 'Bean Chili', kcal=330)]
        planner.replacement_options(plan, entry)
        params = self.api.calls_to('/recipes/complexSearch')[0].params
        self.assertEqual(params['type'], 'main course')
        self.assertEqual(params['diet'], 'vegetarian')
        self.assertEqual(params['intolerances'], 'gluten,peanut')

    def test_other_option_rounds_are_new_searches(self):
        plan = self.make_plan(days=1)
        entry = plan.entries.get(slot='breakfast')
        planner.replacement_options(plan, entry, 0)
        planner.replacement_options(plan, entry, 0)
        planner.replacement_options(plan, entry, 1)
        self.assertEqual(len(self.api.calls_to('/recipes/complexSearch')), 2)

    def test_browse_recipes_builds_the_search(self):
        self.api.search_results = [make_recipe(500 + number, f'Recipe {number}') for number in range(20)]
        cards, total = planner.browse_recipes({
            'q': '', 'meal': 'dinner', 'diet': 'halal', 'max_calories': 600, 'max_minutes': 30,
            'gluten_free': True, 'dairy_free': True, 'sustainable': True,
        }, page=2)
        params = self.api.calls[0].params
        self.assertEqual(params['type'], 'main course')
        self.assertEqual(params['diet'], 'vegetarian')
        self.assertEqual(params['intolerances'], 'gluten,dairy')
        self.assertEqual(params['excludeIngredients'], 'pork,bacon,ham,wine,beer')
        self.assertEqual(params['maxCalories'], 600)
        self.assertEqual(params['maxReadyTime'], 30)
        self.assertEqual(params['sort'], 'popularity')
        self.assertEqual(params['offset'], 8)
        self.assertEqual(params['number'], 8)
        self.assertEqual(len(cards), 8)
        self.assertEqual(total, 20)

    def test_browse_recipes_keeps_the_chosen_diet_with_sustainable(self):
        planner.browse_recipes({'q': 'curry', 'diet': 'pescatarian', 'sustainable': True})
        params = self.api.calls[0].params
        self.assertEqual(params['diet'], 'pescetarian,vegetarian')
        self.assertEqual(params['query'], 'curry')
        self.assertNotIn('sort', params)


class MealPlanModelTests(MealPlanTestCase):
    def test_labels(self):
        plan = self.make_plan(days=7, diet='halal', allergies=['peanut', 'gluten'])
        self.assertEqual(plan.end_date, date(2026, 11, 1))
        self.assertEqual(plan.diet_label, 'Halal not verified')
        self.assertEqual(plan.calorie_label, '1,800 kcal/day')
        self.assertEqual(plan.days_label, '7 days')
        self.assertEqual(plan.allergy_badges, ['No peanuts', 'Gluten free'])
        entry = plan.entries.get(day=3, slot='dinner')
        self.assertEqual(entry.date, date(2026, 10, 28))

    def test_deleting_a_plan_deletes_its_entries(self):
        plan = self.make_plan(days=2)
        plan.delete()
        self.assertFalse(MealPlanEntry.objects.exists())


class AdminTests(MealPlanTestCase):
    def test_admin_lists_and_opens_plans(self):
        plan = self.make_plan(include_snack=True)
        admin = User.objects.create_superuser('boss', 'boss@example.com', self.password)
        self.client.force_login(admin)
        response = self.client.get(reverse('admin:meal_plan_mealplan_changelist'))
        self.assertContains(response, 'Green week')
        response = self.client.get(reverse('admin:meal_plan_mealplan_change', args=[plan.pk]))
        self.assertContains(response, 'recipe_id')
        self.assertEqual(self.api.calls, [])


class LoginRequiredTests(MealPlanTestCase):
    def test_every_page_sends_logged_out_visitors_to_log_in(self):
        plan = self.make_plan()
        entry = plan.entries.first()
        urls = [
            reverse('meal_plan:plan_list'),
            reverse('meal_plan:plan_create'),
            reverse('meal_plan:plan_detail', args=[plan.pk]),
            reverse('meal_plan:meal_replace', args=[plan.pk, entry.pk]),
            reverse('meal_plan:recipes'),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse('login')))
        response = self.client.post(reverse('meal_plan:plan_delete', args=[plan.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MealPlan.objects.filter(pk=plan.pk).exists())
        self.assertEqual(self.api.calls, [])


class PlanListViewTests(MealPlanTestCase):
    def test_empty_list_shows_the_profile_strip_and_empty_state(self):
        self.set_profile(diet='halal')
        self.login()
        response = self.client.get(reverse('meal_plan:plan_list'))
        self.assertContains(response, 'My plans')
        self.assertContains(response, 'Plans use your profile')
        self.assertContains(response, 'Halal')
        self.assertContains(response, 'No allergies set')
        self.assertContains(response, "You don't have a plan yet")
        self.assertContains(response, 'Create your first plan')
        self.assertEqual(self.api.calls, [])

    def test_list_shows_only_your_own_plans(self):
        self.make_plan(name='Green week', diet='vegetarian')
        self.make_plan(user=self.other, name='Someone else')
        self.login()
        response = self.client.get(reverse('meal_plan:plan_list'))
        self.assertContains(response, 'Green week')
        self.assertContains(response, '26 Oct 2026 – 27 Oct 2026 · 2 days')
        self.assertContains(response, 'Vegetarian')
        self.assertContains(response, '1,800 kcal/day')
        self.assertContains(response, 'Open plan')
        self.assertContains(response, '+ Create meal plan')
        self.assertNotContains(response, 'Someone else')
        self.assertNotContains(response, "You don't have a plan yet")


class PlanCreateViewTests(MealPlanTestCase):
    def valid_data(self, **changes):
        data = {
            'name': 'Green week',
            'start_date': '2026-10-26',
            'days': '7',
            'diet': 'vegetarian',
            'allergies': ['gluten'],
            'include_snack': 'on',
            'calorie_goal': '1800',
        }
        data.update(changes)
        return data

    def test_form_is_filled_in_from_the_profile(self):
        self.set_profile(diet='vegan', allergies=['Milk', 'Sesame'], calorie_target=1900, meals_per_day=4)
        self.login()
        response = self.client.get(reverse('meal_plan:plan_create'))
        self.assertContains(response, 'Create a meal plan')
        self.assertContains(response, '<option value="vegan" selected>Vegan</option>', html=True)
        self.assertContains(response, 'value="dairy" class="mealplan-chip-input" data-plan-allergy data-name="Dairy" checked')
        self.assertContains(response, 'Sesame')
        self.assertContains(response, 'data-profile-target="1900"')
        self.assertContains(response, '1,900 kcal/day (from your profile)')
        self.assertContains(response, 'Breakfast, lunch, dinner, snack')
        self.assertContains(response, 'Dairy, Sesame')
        self.assertContains(response, 'Halal')
        self.assertContains(response, 'Skips pork and alcohol')
        self.assertEqual(self.api.calls, [])

    def test_form_shows_the_seven_figma_chips_by_default(self):
        self.login()
        response = self.client.get(reverse('meal_plan:plan_create'))
        for label in ['Gluten free', 'Dairy free', 'Peanuts', 'Tree nuts', 'Eggs', 'Seafood', 'Soy']:
            self.assertContains(response, label)
        self.assertNotContains(response, 'value="sesame"')
        self.assertContains(response, '2,000 kcal/day (general reference)')
        self.assertContains(response, 'Nothing selected')

    def test_valid_form_creates_the_plan_and_opens_it(self):
        self.api.search_results = self.snacks
        self.login()
        response = self.client.post(reverse('meal_plan:plan_create'), self.valid_data(), follow=True)
        plan = MealPlan.objects.get()
        self.assertRedirects(response, reverse('meal_plan:plan_detail', args=[plan.pk]))
        self.assertEqual(plan.user, self.user)
        self.assertEqual(plan.name, 'Green week')
        self.assertEqual(plan.days, 7)
        self.assertEqual(plan.calorie_goal, 1800)
        self.assertEqual(plan.allergies, ['gluten'])
        self.assertContains(response, '“Green week” is ready.')
        self.assertContains(response, 'Overnight Oats')

    def test_invalid_form_shows_errors_without_calling_spoonacular(self):
        self.login()
        response = self.client.post(reverse('meal_plan:plan_create'), self.valid_data(name='  ', days='20', calorie_goal='500'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Give your plan a name.')
        self.assertContains(response, 'Enter a number between 1 and 14.')
        self.assertContains(response, 'Enter a goal between 1,000 and 5,000 kcal.')
        self.assertFalse(MealPlan.objects.exists())
        self.assertEqual(self.api.calls, [])

    def test_spoonacular_problems_show_a_friendly_message(self):
        self.api.failures = {'/mealplanner/generate': 402}
        self.login()
        with self.assertLogs('meal_plan.services.spoonacular', 'WARNING'):
            response = self.client.post(reverse('meal_plan:plan_create'), self.valid_data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'daily limit has been reached')
        self.assertContains(response, 'value="Green week"')
        self.assertFalse(MealPlan.objects.exists())

    def test_plan_without_possible_meals_shows_a_hint(self):
        self.api.short_day = True
        self.login()
        response = self.client.post(reverse('meal_plan:plan_create'), self.valid_data())
        self.assertContains(response, 'Try removing an allergy or choosing another diet.')
        self.assertFalse(MealPlan.objects.exists())

    def test_warns_when_snacks_could_not_be_added(self):
        self.api.search_results = []
        self.login()
        response = self.client.post(reverse('meal_plan:plan_create'), self.valid_data(), follow=True)
        self.assertContains(response, 'this plan has no snacks')


class PlanDetailViewTests(MealPlanTestCase):
    def test_detail_shows_each_day_with_its_meals(self):
        plan = self.make_plan(days=2, diet='vegetarian', allergies=['peanut'], include_snack=True)
        self.login()
        response = self.client.get(reverse('meal_plan:plan_detail', args=[plan.pk]))
        self.assertContains(response, 'Green week')
        self.assertContains(response, '26 Oct 2026 – 27 Oct 2026 · 2 days')
        self.assertContains(response, 'No peanuts')
        self.assertContains(response, 'Jump to')
        self.assertContains(response, 'Mon, 26 Oct')
        self.assertContains(response, 'Overnight Oats')
        self.assertContains(response, '30 min · 310 kcal')
        self.assertContains(response, 'P 11.0 g · C 52.0 g · F 7.0 g')
        self.assertContains(response, '1,296 kcal')
        self.assertContains(response, 'https://img.spoonacular.com/recipes/101-556x370.jpg')
        self.assertContains(response, 'https://example.com/recipes/101')
        self.assertContains(response, 'Delete this plan?')
        self.assertContains(response, 'Recipe data from')
        self.assertEqual(len(self.api.calls_to('/recipes/informationBulk')), 1)

    def test_detail_reuses_cached_recipes(self):
        plan = self.make_plan(days=2)
        self.login()
        self.client.get(reverse('meal_plan:plan_detail', args=[plan.pk]))
        self.client.get(reverse('meal_plan:plan_detail', args=[plan.pk]))
        self.assertEqual(len(self.api.calls), 1)

    def test_halal_plans_say_halal_is_not_verified(self):
        plan = self.make_plan(days=1, diet='halal')
        self.login()
        response = self.client.get(reverse('meal_plan:plan_detail', args=[plan.pk]))
        self.assertContains(response, 'Halal not verified')
        self.assertNotContains(response, '>Halal<')

    def test_detail_survives_spoonacular_being_down(self):
        plan = self.make_plan(days=1)
        self.api.failures = {'/recipes/informationBulk': requests.ConnectionError()}
        self.login()
        with self.assertLogs('meal_plan.services.spoonacular', 'WARNING'):
            response = self.client.get(reverse('meal_plan:plan_detail', args=[plan.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your plan is saved')
        self.assertContains(response, 'Recipe details are not available right now')

    def test_you_cannot_open_someone_elses_plan(self):
        plan = self.make_plan(user=self.other)
        self.login()
        response = self.client.get(reverse('meal_plan:plan_detail', args=[plan.pk]))
        self.assertEqual(response.status_code, 404)


class ReplaceMealViewTests(MealPlanTestCase):
    def setUp(self):
        super().setUp()
        self.plan = self.make_plan(days=1)
        self.entry = self.plan.entries.get(slot='breakfast')
        self.api.search_results = [
            make_recipe(402, 'Yogurt Parfait', kcal=300, protein=14),
            make_recipe(403, 'Avocado Toast', kcal=330, protein=11),
            make_recipe(404, 'Banana Pancakes', kcal=360, protein=9),
        ]
        self.url = reverse('meal_plan:meal_replace', args=[self.plan.pk, self.entry.pk])
        self.login()

    def test_partial_lists_three_options(self):
        response = self.client.get(self.url, {'partial': '1'})
        self.assertTemplateUsed(response, 'meal_plan/includes/replace_panel.html')
        self.assertTemplateNotUsed(response, 'base.html')
        self.assertContains(response, 'Replace breakfast')
        self.assertContains(response, 'Day 1 · Mon, 26 Oct. Pick another recipe that fits your plan (about 310 kcal).')
        self.assertContains(response, 'Current meal')
        self.assertContains(response, 'Overnight Oats · 310 kcal')
        self.assertContains(response, 'Yogurt Parfait')
        self.assertContains(response, '30 min · 300 kcal · P 14 g')
        self.assertContains(response, 'Fits your diet', count=3)
        self.assertContains(response, 'Show other options')
        self.assertEqual(self.client.session['meal_plan_offers'][str(self.entry.pk)], [402, 403, 404])

    def test_choosing_an_offered_recipe_replaces_the_meal(self):
        self.client.get(self.url, {'partial': '1'})
        response = self.client.post(self.url, {'recipe_id': '403'})
        self.assertRedirects(response, reverse('meal_plan:plan_detail', args=[self.plan.pk]) + '#day-1', fetch_redirect_response=False)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.recipe_id, 403)
        detail = self.client.get(reverse('meal_plan:plan_detail', args=[self.plan.pk]))
        self.assertContains(detail, 'Avocado Toast')
        self.assertContains(detail, 'Breakfast on day 1 was replaced.')
        self.assertNotIn(str(self.entry.pk), self.client.session['meal_plan_offers'])

    def test_recipes_that_were_not_offered_are_refused(self):
        self.client.get(self.url, {'partial': '1'})
        response = self.client.post(self.url, {'recipe_id': '999999'}, follow=True)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.recipe_id, 101)
        self.assertContains(response, 'no longer on offer')

    def test_full_page_works_without_javascript(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'meal_plan/replace_meal.html')
        self.assertContains(response, '?round=1')
        self.assertContains(response, 'Green week')

    def test_spoonacular_problems_show_inside_the_panel(self):
        self.api.failures = {'/recipes/complexSearch': 402}
        with self.assertLogs('meal_plan.services.spoonacular', 'WARNING'):
            response = self.client.get(self.url, {'partial': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'daily limit has been reached')
        self.assertNotContains(response, 'name="recipe_id"')

    def test_someone_elses_meal_is_not_found(self):
        plan = self.make_plan(user=self.other)
        entry = plan.entries.first()
        response = self.client.get(reverse('meal_plan:meal_replace', args=[plan.pk, entry.pk]))
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse('meal_plan:meal_replace', args=[self.plan.pk, entry.pk]))
        self.assertEqual(response.status_code, 404)


class DeletePlanViewTests(MealPlanTestCase):
    def test_delete_needs_post(self):
        plan = self.make_plan()
        self.login()
        response = self.client.get(reverse('meal_plan:plan_delete', args=[plan.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(MealPlan.objects.filter(pk=plan.pk).exists())

    def test_delete_removes_the_plan(self):
        plan = self.make_plan()
        self.login()
        response = self.client.post(reverse('meal_plan:plan_delete', args=[plan.pk]), follow=True)
        self.assertRedirects(response, reverse('meal_plan:plan_list'))
        self.assertContains(response, '“Green week” was deleted.')
        self.assertFalse(MealPlan.objects.exists())
        self.assertFalse(MealPlanEntry.objects.exists())

    def test_you_cannot_delete_someone_elses_plan(self):
        plan = self.make_plan(user=self.other)
        self.login()
        response = self.client.post(reverse('meal_plan:plan_delete', args=[plan.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(MealPlan.objects.filter(pk=plan.pk).exists())


class RecipesViewTests(MealPlanTestCase):
    def setUp(self):
        super().setUp()
        self.api.search_results = [
            make_recipe(600 + number, f'Recipe {number}', vegetarian=True, glutenFree=number % 2 == 0)
            for number in range(20)
        ]
        self.login()

    def test_recipes_page_shows_cards_filters_and_load_more(self):
        response = self.client.get(reverse('meal_plan:recipes'))
        self.assertContains(response, 'Recipes')
        self.assertContains(response, 'Apply filters')
        self.assertContains(response, 'Any meal')
        self.assertContains(response, 'Sustainable')
        self.assertContains(response, 'Recipe 0')
        self.assertContains(response, 'Recipe 7')
        self.assertNotContains(response, 'Recipe 8<')
        self.assertContains(response, '8 of 20 recipes match your filters.')
        self.assertContains(response, 'Load more recipes')
        self.assertContains(response, '?page=2')
        self.assertContains(response, '<span class="badge badge-success">Vegetarian</span>', html=True)

    def test_load_more_without_javascript_shows_all_pages(self):
        response = self.client.get(reverse('meal_plan:recipes'), {'page': '2'})
        self.assertContains(response, 'Recipe 15')
        self.assertContains(response, '16 of 20 recipes match your filters.')
        self.assertEqual(len(self.api.calls), 2)

    def test_load_more_with_javascript_returns_the_next_page_only(self):
        response = self.client.get(reverse('meal_plan:recipes'), {'page': '3', 'partial': '1'})
        data = response.json()
        self.assertIn('Recipe 16', data['html'])
        self.assertNotIn('Recipe 15', data['html'])
        self.assertEqual(data['next_url'], '')
        self.assertEqual(data['count'], '20 of 20 recipes match your filters.')

    def test_filters_are_sent_to_spoonacular(self):
        self.client.get(reverse('meal_plan:recipes'), {'q': 'oats', 'meal': 'breakfast', 'diet': 'vegan', 'max_minutes': '20', 'gluten_free': 'on'})
        params = self.api.calls[0].params
        self.assertEqual(params['query'], 'oats')
        self.assertEqual(params['type'], 'breakfast')
        self.assertEqual(params['diet'], 'vegan')
        self.assertEqual(params['maxReadyTime'], 20)
        self.assertEqual(params['intolerances'], 'gluten')

    def test_invalid_filters_do_not_call_spoonacular(self):
        response = self.client.get(reverse('meal_plan:recipes'), {'max_calories': '9'})
        self.assertContains(response, 'Enter a number from 50 to 3,000.')
        self.assertContains(response, 'Fix the filters above')
        self.assertEqual(self.api.calls, [])

    def test_halal_filter_marks_recipes_as_not_verified(self):
        response = self.client.get(reverse('meal_plan:recipes'), {'diet': 'halal'})
        self.assertContains(response, 'Halal not verified')
        self.assertEqual(self.api.calls[0].params['excludeIngredients'], 'pork,bacon,ham,wine,beer')

    def test_no_results_shows_the_empty_state(self):
        self.api.search_results = []
        response = self.client.get(reverse('meal_plan:recipes'), {'q': 'zzzz'})
        self.assertContains(response, 'No recipes match your filters')

    def test_spoonacular_problems_show_a_friendly_message(self):
        self.api.failures = {'/recipes/complexSearch': requests.Timeout()}
        with self.assertLogs('meal_plan.services.spoonacular', 'WARNING'):
            response = self.client.get(reverse('meal_plan:recipes'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Recipe data is not available right now')
