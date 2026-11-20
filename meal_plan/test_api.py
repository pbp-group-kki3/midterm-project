from rest_framework.test import APIClient

from meal_plan.models import MealPlan, MealPlanEntry
from meal_plan.services.spoonacular import MESSAGES
from meal_plan.tests import MealPlanTestCase, make_recipe

API = '/api/meal-plans/'


class MealPlanAPITests(MealPlanTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def plan_data(self, **changes):
        data = {
            'name': 'App week',
            'start_date': '2026-11-23',
            'days': 2,
            'diet': ['vegetarian'],
            'allergies': ['gluten'],
            'include_snack': False,
            'calorie_goal': 1800,
        }
        data.update(changes)
        return data

    def test_every_endpoint_needs_login(self):
        plan = self.make_plan()
        entry = plan.entries.first()
        for url in [API, f'{API}{plan.pk}/', f'{API}{plan.pk}/meals/{entry.pk}/options/', f'{API}recipes/', f'{API}form-options/']:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.assertEqual(self.client.post(API, self.plan_data(), format='json').status_code, 403)
        self.assertEqual(self.client.delete(f'{API}{plan.pk}/').status_code, 403)
        self.assertTrue(MealPlan.objects.filter(pk=plan.pk).exists())
        self.assertEqual(self.api.calls, [])

    def test_list_shows_only_my_plans(self):
        self.make_plan(name='Mine')
        self.make_plan(user=self.other, name='Theirs')
        self.login()
        response = self.client.get(API)
        self.assertEqual(response.status_code, 200)
        plans = response.json()
        self.assertEqual([plan['name'] for plan in plans], ['Mine'])
        self.assertEqual(plans[0]['meal_count'], 6)
        self.assertEqual(plans[0]['start_date'], '2026-10-26')
        self.assertEqual(plans[0]['end_date'], '2026-10-27')
        self.assertEqual(self.api.calls, [])

    def test_create_plan(self):
        self.login()
        response = self.client.post(API, self.plan_data(allergies=['soy', 'gluten']), format='json')
        self.assertEqual(response.status_code, 201)
        plan = MealPlan.objects.get()
        self.assertEqual(plan.user, self.user)
        self.assertEqual(plan.name, 'App week')
        self.assertEqual(plan.diets, ['vegetarian'])
        self.assertEqual(plan.allergies, ['gluten', 'soy'])
        self.assertEqual(plan.entries.count(), 6)
        data = response.json()
        self.assertEqual(data['id'], plan.pk)
        self.assertEqual(data['allergy_labels'], ['Gluten free', 'No soy'])
        self.assertIsNone(data['warning'])

    def test_create_rejects_bad_input(self):
        self.login()
        response = self.client.post(API, self.plan_data(name='   ', days=30, diet=['ketogenic', 'vegan'], calorie_goal=50), format='json')
        self.assertEqual(response.status_code, 400)
        errors = response.json()
        self.assertEqual(errors['name'], ['Give your plan a name.'])
        self.assertEqual(errors['days'], ['Enter a number between 1 and 14.'])
        self.assertEqual(errors['diet'], ["Ketogenic can't be combined with vegetarian, vegan or pescatarian in one plan."])
        self.assertEqual(errors['calorie_goal'], ['Enter a goal between 1,000 and 5,000 kcal.'])
        self.assertFalse(MealPlan.objects.exists())
        self.assertEqual(self.api.calls, [])

    def test_create_when_spoonacular_is_out_of_points(self):
        self.api.failures['/mealplanner'] = 402
        self.login()
        response = self.client.post(API, self.plan_data(), format='json')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['detail'], MESSAGES['quota'])
        self.assertFalse(MealPlan.objects.exists())

    def test_create_when_no_full_plan_fits_the_choices(self):
        self.api.short_day = True
        self.login()
        response = self.client.post(API, self.plan_data(), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Try removing an allergy or choosing another diet.', response.json()['detail'])
        self.assertFalse(MealPlan.objects.exists())

    def test_detail_returns_the_schedule(self):
        plan = self.make_plan()
        self.login()
        response = self.client.get(f'{API}{plan.pk}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['schedule']), 2)
        first = data['schedule'][0]
        self.assertEqual(first['day'], 1)
        self.assertEqual(first['date'], '2026-10-26')
        self.assertEqual([meal['slot'] for meal in first['meals']], ['breakfast', 'lunch', 'dinner'])
        self.assertEqual(first['meals'][0]['recipe']['title'], 'Overnight Oats')
        self.assertEqual(first['calories'], 310 + 320 + 486)
        self.assertIsNone(data['error'])

    def test_detail_still_answers_when_spoonacular_is_down(self):
        self.api.failures['/recipes/informationBulk'] = 500
        plan = self.make_plan()
        self.login()
        response = self.client.get(f'{API}{plan.pk}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        meal = data['schedule'][0]['meals'][0]
        self.assertFalse(meal['recipe']['available'])
        self.assertIsNone(meal['recipe']['calories'])
        self.assertEqual(data['error'], MESSAGES['unavailable'])

    def test_someone_elses_plan_is_not_found(self):
        plan = self.make_plan(user=self.other)
        entry = plan.entries.first()
        self.login()
        self.assertEqual(self.client.get(f'{API}{plan.pk}/').status_code, 404)
        self.assertEqual(self.client.patch(f'{API}{plan.pk}/', {'name': 'Mine now'}, format='json').status_code, 404)
        self.assertEqual(self.client.delete(f'{API}{plan.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'{API}{plan.pk}/meals/{entry.pk}/options/').status_code, 404)
        plan.refresh_from_db()
        self.assertEqual(plan.name, 'Green week')

    def test_patch_renames_without_new_meals(self):
        plan = self.make_plan()
        before = list(plan.entries.values_list('recipe_id', flat=True))
        self.login()
        response = self.client.patch(f'{API}{plan.pk}/', {'name': '  Renamed   week '}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['new_meals'])
        plan.refresh_from_db()
        self.assertEqual(plan.name, 'Renamed week')
        self.assertEqual(list(plan.entries.values_list('recipe_id', flat=True)), before)
        self.assertEqual(self.api.calls, [])

    def test_patch_also_takes_form_data(self):
        plan = self.make_plan()
        self.login()
        response = self.client.patch(f'{API}{plan.pk}/', {'allergies': ['soy', 'gluten']}, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['new_meals'])
        plan.refresh_from_db()
        self.assertEqual(plan.allergies, ['gluten', 'soy'])

    def test_put_with_more_days_picks_new_meals(self):
        plan = self.make_plan()
        self.login()
        response = self.client.put(f'{API}{plan.pk}/', self.plan_data(days=3, diet=[], allergies=[]), format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['new_meals'])
        plan.refresh_from_db()
        self.assertEqual(plan.days, 3)
        self.assertEqual(plan.entries.count(), 9)

    def test_failed_edit_leaves_the_plan_alone(self):
        plan = self.make_plan()
        before = list(plan.entries.values_list('recipe_id', flat=True))
        self.api.failures['/mealplanner'] = 500
        self.login()
        response = self.client.patch(f'{API}{plan.pk}/', {'days': 5}, format='json')
        self.assertEqual(response.status_code, 503)
        plan.refresh_from_db()
        self.assertEqual(plan.days, 2)
        self.assertEqual(list(plan.entries.values_list('recipe_id', flat=True)), before)

    def test_delete(self):
        plan = self.make_plan()
        self.login()
        self.assertEqual(self.client.delete(f'{API}{plan.pk}/').status_code, 204)
        self.assertFalse(MealPlan.objects.exists())
        self.assertFalse(MealPlanEntry.objects.exists())

    def test_replace_a_meal_with_an_offered_recipe(self):
        plan = self.make_plan()
        entry = plan.entries.get(day=1, slot='lunch')
        self.api.search_results = list(self.api.add(
            make_recipe(401, 'Bean Wrap', kcal=330),
            make_recipe(402, 'Pea Risotto', kcal=520),
        ))
        self.login()
        options = self.client.get(f'{API}{plan.pk}/meals/{entry.pk}/options/').json()
        self.assertEqual(options['current']['id'], 201)
        self.assertEqual([option['id'] for option in options['options']], [401, 402])
        self.assertEqual(options['next_round'], 1)
        response = self.client.post(f'{API}{plan.pk}/meals/{entry.pk}/replace/', {'recipe_id': 401}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['recipe']['title'], 'Bean Wrap')
        entry.refresh_from_db()
        self.assertEqual(entry.recipe_id, 401)
        again = self.client.post(f'{API}{plan.pk}/meals/{entry.pk}/replace/', {'recipe_id': 402}, format='json')
        self.assertEqual(again.status_code, 400)

    def test_replace_refuses_a_recipe_that_was_not_offered(self):
        plan = self.make_plan()
        entry = plan.entries.get(day=1, slot='lunch')
        self.login()
        response = self.client.post(f'{API}{plan.pk}/meals/{entry.pk}/replace/', {'recipe_id': 999}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'], 'That recipe is no longer on offer. Please pick again.')
        entry.refresh_from_db()
        self.assertEqual(entry.recipe_id, 201)

    def test_recipe_search(self):
        self.api.search_results = self.snacks
        self.login()
        response = self.client.get(f'{API}recipes/?q=apple&meal=snack')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([recipe['title'] for recipe in data['results']], ['Apple Oat Bars', 'Mango Lassi', 'Roasted Chickpeas'])
        self.assertEqual(data['page'], 1)
        self.assertIsNone(data['next_page'])
        search = self.api.calls_to('/recipes/complexSearch')[0]
        self.assertEqual(search.params['query'], 'apple')
        self.assertEqual(search.params['type'], 'snack')

    def test_options_and_search_report_spoonacular_failures(self):
        plan = self.make_plan()
        entry = plan.entries.get(day=1, slot='lunch')
        self.api.failures['/recipes/complexSearch'] = 401
        self.login()
        options = self.client.get(f'{API}{plan.pk}/meals/{entry.pk}/options/')
        self.assertEqual(options.status_code, 503)
        self.assertEqual(options.json()['detail'], MESSAGES['unauthorized'])
        search = self.client.get(f'{API}recipes/')
        self.assertEqual(search.status_code, 503)
        self.assertEqual(search.json()['detail'], MESSAGES['unauthorized'])

    def test_recipe_search_rejects_bad_filters(self):
        self.login()
        response = self.client.get(f'{API}recipes/?max_calories=10')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['max_calories'], ['Enter a number from 50 to 3,000.'])
        self.assertEqual(self.api.calls, [])

    def test_form_options_follow_the_profile(self):
        self.set_profile(diet=['vegan'], calorie_target=1900)
        self.login()
        data = self.client.get(f'{API}form-options/').json()
        self.assertEqual(data['defaults']['diet'], ['vegan'])
        self.assertEqual(data['calorie_goal']['default'], 1900)
        self.assertEqual(data['days'], {'min': 1, 'max': 14, 'default': 7})
        self.assertIn({'key': 'halal', 'label': 'Halal'}, data['diets'])
        self.assertEqual(self.api.calls, [])

    def test_app_can_write_without_a_csrf_token(self):
        plan = self.make_plan()
        entry = plan.entries.get(day=1, slot='lunch')
        self.api.search_results = list(self.api.add(make_recipe(401, 'Bean Wrap', kcal=330)))
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(API, self.plan_data(), format='json').status_code, 201)
        self.assertEqual(client.patch(f'{API}{plan.pk}/', {'name': 'Renamed'}, format='json').status_code, 200)
        self.assertEqual(client.get(f'{API}{plan.pk}/meals/{entry.pk}/options/').status_code, 200)
        self.assertEqual(client.post(f'{API}{plan.pk}/meals/{entry.pk}/replace/', {'recipe_id': 401}, format='json').status_code, 200)
        self.assertEqual(client.delete(f'{API}{plan.pk}/').status_code, 204)
        self.assertEqual(list(MealPlan.objects.values_list('name', flat=True)), ['App week'])
