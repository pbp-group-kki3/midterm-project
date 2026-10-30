import datetime
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from django.core.management import call_command
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError

from food_of_the_day.models import MealOfTheDay, MealComment, SavedMeal
from food_of_the_day.forms import MealCommentForm
from food_of_the_day.services import (
    get_recipe,
    extract_calories,
    get_did_you_know,
    extract_ingredients,
    extract_instructions,
    is_safe_external_url,
)

User = get_user_model()


class MealOfTheDayModelTest(TestCase):
    def setUp(self):
        self.today = datetime.date.today()
        self.meal = MealOfTheDay.objects.create(date=self.today, recipe_id=716429)

    def test_meal_creation(self):
        self.assertEqual(self.meal.recipe_id, 716429)
        self.assertEqual(self.meal.date, self.today)
        self.assertIn("Meal of the Day for", str(self.meal))

    def test_unique_date_constraint(self):
        with self.assertRaises(IntegrityError):
            MealOfTheDay.objects.create(date=self.today, recipe_id=123456)


class MealCommentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.meal = MealOfTheDay.objects.create(date=datetime.date.today(), recipe_id=716429)
        self.comment = MealComment.objects.create(
            user=self.user,
            meal=self.meal,
            text='Great sustainable meal idea!'
        )

    def test_comment_creation(self):
        self.assertEqual(self.comment.user, self.user)
        self.assertEqual(self.comment.meal, self.meal)
        self.assertIn('testuser', str(self.comment))


class SavedMealModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='saveuser', password='password123')
        self.meal = MealOfTheDay.objects.create(date=datetime.date.today(), recipe_id=716429)
        self.saved_meal = SavedMeal.objects.create(
            user=self.user,
            meal=self.meal,
            recipe_title="Pasta with Garlic"
        )

    def test_saved_meal_creation(self):
        self.assertEqual(self.saved_meal.user, self.user)
        self.assertEqual(self.saved_meal.meal, self.meal)
        self.assertEqual(self.saved_meal.recipe_title, "Pasta with Garlic")
        self.assertIn("saveuser", str(self.saved_meal))

    def test_unique_user_meal_constraint(self):
        with self.assertRaises(IntegrityError):
            SavedMeal.objects.create(
                user=self.user,
                meal=self.meal,
                recipe_title="Duplicate Save"
            )



class FoodOfTheDayServicesTest(TestCase):
    def setUp(self):
        cache.clear()
        self.sample_recipe = {
            "id": 716429,
            "title": "Pasta with Garlic, Scallions, Cauliflower & Breadcrumbs",
            "image": "https://spoonacular.com/recipeImages/716429-556x370.jpg",
            "readyInMinutes": 45,
            "servings": 2,
            "sourceName": "Full Belly Sisters",
            "sourceUrl": "http://fullbellysisters.blogspot.com/2012/06/pasta-w-garlic-scallions-cauliflower.html",
            "dishTypes": ["lunch", "main course", "dinner"],
            "extendedIngredients": [
                {"original": "2 tbsp olive oil", "name": "olive oil"},
                {"original": "1 head cauliflower", "name": "cauliflower"}
            ],
            "analyzedInstructions": [
                {
                    "steps": [
                        {"number": 1, "step": "Cut the cauliflower into florets."},
                        {"number": 2, "step": "Sauté in olive oil until golden."}
                    ]
                }
            ],
            "nutrition": {
                "nutrients": [
                    {"name": "Calories", "amount": 584.2, "unit": "kcal", "percentOfDailyNeeds": 29.2},
                    {"name": "Fat", "amount": 20.0, "unit": "g", "percentOfDailyNeeds": 30.8},
                    {"name": "Carbohydrates", "amount": 80.0, "unit": "g", "percentOfDailyNeeds": 26.7},
                    {"name": "Sugar", "amount": 7.0, "unit": "g", "percentOfDailyNeeds": 7.8},
                    {"name": "Sodium", "amount": 500.0, "unit": "mg", "percentOfDailyNeeds": 21.7},
                    {"name": "Cholesterol", "amount": 10.0, "unit": "mg", "percentOfDailyNeeds": 3.3},
                    {"name": "Vitamin C", "amount": 120.0, "unit": "mg", "percentOfDailyNeeds": 145.5},
                    {"name": "Vitamin K", "amount": 80.0, "unit": "µg", "percentOfDailyNeeds": 90.0},
                    {"name": "Iron", "amount": 3.5, "unit": "mg", "percentOfDailyNeeds": 19.4},
                ]
            }
        }

    def test_extract_calories(self):
        cal = extract_calories(self.sample_recipe)
        self.assertEqual(cal, 584)

    def test_extract_ingredients(self):
        ingredients = extract_ingredients(self.sample_recipe)
        self.assertEqual(len(ingredients), 2)
        self.assertEqual(ingredients[0], "2 tbsp olive oil")

    def test_extract_instructions(self):
        steps = extract_instructions(self.sample_recipe)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0], "Cut the cauliflower into florets.")

    def test_get_did_you_know_selects_top_two_micronutrients(self):
        facts = get_did_you_know(self.sample_recipe)
        self.assertEqual(len(facts), 2)
        self.assertIn("146% of your daily Vitamin C", facts[0])
        self.assertIn("90% of your daily Vitamin K", facts[1])

    def test_get_did_you_know_ignores_alcohol_and_non_vitamins(self):
        recipe_with_alcohol = {
            "nutrition": {
                "nutrients": [
                    {"name": "Alcohol %", "amount": 2.5, "unit": "%", "percentOfDailyNeeds": 100.0},
                    {"name": "Alcohol", "amount": 2.5, "unit": "g", "percentOfDailyNeeds": 100.0},
                    {"name": "Caffeine", "amount": 50.0, "unit": "mg", "percentOfDailyNeeds": 50.0},
                    {"name": "Vitamin C", "amount": 60.0, "unit": "mg", "percentOfDailyNeeds": 80.0},
                    {"name": "Calcium", "amount": 200.0, "unit": "mg", "percentOfDailyNeeds": 25.0},
                ]
            }
        }
        facts = get_did_you_know(recipe_with_alcohol)
        self.assertEqual(len(facts), 2)
        self.assertIn("Vitamin C", facts[0])
        self.assertIn("Calcium", facts[1])
        for fact in facts:
            self.assertNotIn("Alcohol", fact)
            self.assertNotIn("Caffeine", fact)

    def test_get_did_you_know_empty_when_no_qualifying_nutrients(self):
        empty_recipe = {
            "nutrition": {
                "nutrients": [
                    {"name": "Calories", "amount": 200, "percentOfDailyNeeds": 10},
                    {"name": "Fat", "amount": 10, "percentOfDailyNeeds": 15},
                ]
            }
        }
        facts = get_did_you_know(empty_recipe)
        self.assertEqual(facts, [])

    @patch('food_of_the_day.services._get_recipe_from_meal_plan', None)
    @patch('food_of_the_day.services._fallback_get')
    def test_get_recipe_caching(self, mock_fallback_get):
        mock_fallback_get.return_value = self.sample_recipe

        res1 = get_recipe(716429)
        self.assertEqual(res1['id'], 716429)
        mock_fallback_get.assert_called_once()

        res2 = get_recipe(716429)
        self.assertEqual(res2['id'], 716429)
        mock_fallback_get.assert_called_once()

    def test_safe_external_url(self):
        self.assertTrue(is_safe_external_url("https://spoonacular.com/recipe"))
        self.assertTrue(is_safe_external_url("http://example.com"))
        self.assertFalse(is_safe_external_url("javascript:alert(1)"))
        self.assertFalse(is_safe_external_url("data:text/html,<script>alert(1)</script>"))
        self.assertFalse(is_safe_external_url(""))
        self.assertFalse(is_safe_external_url(None))

    def test_get_recipe_invalid_id_returns_none(self):
        self.assertIsNone(get_recipe(-1))
        self.assertIsNone(get_recipe("invalid_string"))
        self.assertIsNone(get_recipe(0))

    @patch('food_of_the_day.services._get_recipe_from_meal_plan', None)
    @patch('food_of_the_day.services._fallback_get')
    def test_get_recipe_negative_caching(self, mock_fallback_get):
        mock_fallback_get.return_value = None
        # First call hits fallback_get
        result1 = get_recipe(999999)
        self.assertIsNone(result1)
        self.assertEqual(mock_fallback_get.call_count, 1)

        # Second call should be served from negative cache, avoiding network hit
        result2 = get_recipe(999999)
        self.assertIsNone(result2)
        self.assertEqual(mock_fallback_get.call_count, 1)


class FoodOfTheDayFormsTest(TestCase):
    def test_form_valid_text(self):
        form = MealCommentForm(data={'text': 'Very nutritious and tasty!'})
        self.assertTrue(form.is_valid())

    def test_form_whitespace_only_invalid(self):
        form = MealCommentForm(data={'text': '     \n   '})
        self.assertFalse(form.is_valid())
        self.assertIn('text', form.errors)

    def test_form_too_short_invalid(self):
        form = MealCommentForm(data={'text': 'a'})
        self.assertFalse(form.is_valid())

    def test_form_too_long_invalid(self):
        form = MealCommentForm(data={'text': 'a' * 1001})
        self.assertFalse(form.is_valid())

    def test_form_control_characters_stripped(self):
        form = MealCommentForm(data={'text': 'Delicious!\x08\x1f Great choice!'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['text'], 'Delicious! Great choice!')

    def test_form_null_bytes_rejected(self):
        form = MealCommentForm(data={'text': 'Delicious!\x00 Great choice!'})
        self.assertFalse(form.is_valid())
        self.assertIn('text', form.errors)


@override_settings(ROOT_URLCONF='food_of_the_day.test_urls')
class FoodOfTheDayViewsTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.today = datetime.date.today()
        self.meal = MealOfTheDay.objects.create(date=self.today, recipe_id=716429)
        self.user = User.objects.create_user(username='dineder', password='password123')
        self.sample_recipe = {
            "id": 716429,
            "title": "Healthy Green Bowl",
            "image": "https://spoonacular.com/sample.jpg",
            "readyInMinutes": 30,
            "servings": 2,
            "sourceName": "SpoonFed Kitchen",
            "sourceUrl": "https://spoonfed.example.com",
            "dishTypes": ["lunch"],
            "extendedIngredients": [{"original": "1 cup spinach"}],
            "analyzedInstructions": [{"steps": [{"step": "Mix everything in a bowl."}]}],
            "nutrition": {
                "nutrients": [
                    {"name": "Calories", "amount": 350.0},
                    {"name": "Iron", "amount": 5.0, "percentOfDailyNeeds": 50.0}
                ]
            }
        }

    @patch('food_of_the_day.views.get_recipe')
    def test_index_view(self, mock_get_recipe):
        mock_get_recipe.return_value = self.sample_recipe
        response = self.client.get(reverse('food_of_the_day:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Healthy Green Bowl")

    @patch('food_of_the_day.views.get_recipe')
    def test_detail_view_anonymous_user(self, mock_get_recipe):
        mock_get_recipe.return_value = self.sample_recipe
        response = self.client.get(reverse('food_of_the_day:detail', args=[self.meal.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log in to see the recipe")
        self.assertNotContains(response, "Mix everything in a bowl.")
        self.assertNotContains(response, "Ingredients (serves")

    @patch('food_of_the_day.views.get_recipe')
    def test_detail_view_authenticated_user(self, mock_get_recipe):
        mock_get_recipe.return_value = self.sample_recipe
        self.client.login(username='dineder', password='password123')
        response = self.client.get(reverse('food_of_the_day:detail', args=[self.meal.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Steps")
        self.assertContains(response, "Mix everything in a bowl.")
        self.assertContains(response, "Ingredients (serves")
        self.assertContains(response, "1 cup spinach")

    @patch('food_of_the_day.views.get_recipe')
    def test_xss_url_sanitization(self, mock_get_recipe):
        malicious_recipe = {
            **self.sample_recipe,
            "sourceUrl": "javascript:alert('xss')",
            "image": "javascript:void(0)",
        }
        mock_get_recipe.return_value = malicious_recipe
        response = self.client.get(reverse('food_of_the_day:detail', args=[self.meal.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "javascript:alert('xss')")
        self.assertNotContains(response, "javascript:void(0)")

    def test_add_comment_anonymous_redirects(self):
        response = self.client.post(
            reverse('food_of_the_day:add_comment', args=[self.meal.id]),
            {'text': 'Looks delicious!'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MealComment.objects.count(), 0)

    def test_add_comment_authenticated(self):
        self.client.login(username='dineder', password='password123')
        response = self.client.post(
            reverse('food_of_the_day:add_comment', args=[self.meal.id]),
            {'text': 'Loved this recipe, very eco-friendly!'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MealComment.objects.count(), 1)
        comment = MealComment.objects.first()
        self.assertEqual(comment.user, self.user)
        self.assertEqual(comment.text, 'Loved this recipe, very eco-friendly!')

    def test_add_comment_open_redirect_protection(self):
        self.client.login(username='dineder', password='password123')
        response = self.client.post(
            reverse('food_of_the_day:add_comment', args=[self.meal.id]),
            {'text': 'Testing redirect vulnerability protection.'},
            HTTP_REFERER='https://evil-phishing-site.attacker.com/steal-credentials'
        )
        self.assertEqual(response.status_code, 302)
        # Must NOT redirect to external phishing site
        self.assertFalse(response['Location'].startswith('https://evil-phishing-site'))
        self.assertTrue(response['Location'].startswith(f'/food-of-the-day/{self.meal.id}/'))

    def test_add_comment_duplicate_spam_protection(self):
        self.client.login(username='dineder', password='password123')
        # First submission
        self.client.post(
            reverse('food_of_the_day:add_comment', args=[self.meal.id]),
            {'text': 'Repeated comment text'}
        )
        self.assertEqual(MealComment.objects.count(), 1)

        # Immediate duplicate submission
        response2 = self.client.post(
            reverse('food_of_the_day:add_comment', args=[self.meal.id]),
            {'text': 'Repeated comment text'}
        )
        # Should not create a second identical comment
        self.assertEqual(MealComment.objects.count(), 1)

    def test_add_comment_ajax_success(self):
        self.client.login(username='dineder', password='password123')
        response = self.client.post(
            reverse('food_of_the_day:add_comment', args=[self.meal.id]),
            {'text': 'Asynchronous comment via AJAX.'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['comment']['user'], 'dineder')
        self.assertEqual(data['comment']['text'], 'Asynchronous comment via AJAX.')
        self.assertEqual(MealComment.objects.count(), 1)

    def test_add_comment_ajax_duplicate_rejected(self):
        self.client.login(username='dineder', password='password123')
        # First comment
        self.client.post(
            reverse('food_of_the_day:add_comment', args=[self.meal.id]),
            {'text': 'Fast spam comment test.'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        # Immediate duplicate via AJAX
        response2 = self.client.post(
            reverse('food_of_the_day:add_comment', args=[self.meal.id]),
            {'text': 'Fast spam comment test.'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response2.status_code, 429)
        data = response2.json()
        self.assertIn('error', data)
        self.assertEqual(MealComment.objects.count(), 1)

    @patch('food_of_the_day.views.get_recipe')
    def test_slide_partial_view(self, mock_get_recipe):
        mock_get_recipe.return_value = self.sample_recipe
        response = self.client.get(reverse('food_of_the_day:slide_partial'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Healthy Green Bowl")

    def test_toggle_save_meal_requires_login(self):
        response = self.client.post(
            reverse('food_of_the_day:toggle_save_meal', args=[self.meal.id]),
            {'recipe_title': 'Healthy Green Bowl'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/profiles/login/', response['Location'])
        self.assertEqual(SavedMeal.objects.count(), 0)

    @patch('food_of_the_day.views.get_recipe')
    def test_toggle_save_meal_authenticated(self, mock_get_recipe):
        mock_get_recipe.return_value = self.sample_recipe
        self.client.login(username='dineder', password='password123')

        # First toggle: Save
        response = self.client.post(
            reverse('food_of_the_day:toggle_save_meal', args=[self.meal.id]),
            {'recipe_title': 'Healthy Green Bowl'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SavedMeal.objects.filter(user=self.user, meal=self.meal).exists())
        saved = SavedMeal.objects.get(user=self.user, meal=self.meal)
        self.assertEqual(saved.recipe_title, 'Healthy Green Bowl')

        # Second toggle: Unsave
        response2 = self.client.post(
            reverse('food_of_the_day:toggle_save_meal', args=[self.meal.id])
        )
        self.assertEqual(response2.status_code, 302)
        self.assertFalse(SavedMeal.objects.filter(user=self.user, meal=self.meal).exists())

    @patch('food_of_the_day.views.get_recipe')
    def test_toggle_save_meal_ajax(self, mock_get_recipe):
        mock_get_recipe.return_value = self.sample_recipe
        self.client.login(username='dineder', password='password123')

        response = self.client.post(
            reverse('food_of_the_day:toggle_save_meal', args=[self.meal.id]),
            {'recipe_title': 'Healthy Green Bowl'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['saved'])
        self.assertEqual(data['meal_id'], self.meal.id)

    @patch('food_of_the_day.views.get_recipe')
    def test_toggle_save_meal_sanitizes_title(self, mock_get_recipe):
        mock_get_recipe.return_value = self.sample_recipe
        self.client.login(username='dineder', password='password123')
        # Even if attacker sends malicious title in POST, canonical title is prioritized
        response = self.client.post(
            reverse('food_of_the_day:toggle_save_meal', args=[self.meal.id]),
            {'recipe_title': '<script>alert("xss")</script> Malicious'}
        )
        self.assertEqual(response.status_code, 302)
        saved = SavedMeal.objects.get(user=self.user, meal=self.meal)
        self.assertEqual(saved.recipe_title, 'Healthy Green Bowl')
        self.assertNotIn('<script>', saved.recipe_title)

    @patch('food_of_the_day.views.get_recipe')
    def test_is_saved_in_context(self, mock_get_recipe):
        mock_get_recipe.return_value = self.sample_recipe
        self.client.login(username='dineder', password='password123')

        # Initially not saved
        res = self.client.get(reverse('food_of_the_day:detail', args=[self.meal.id]))
        self.assertFalse(res.context['is_saved'])

        # Save meal
        SavedMeal.objects.create(user=self.user, meal=self.meal, recipe_title="Healthy Green Bowl")

        # Now context reflects saved state
        res2 = self.client.get(reverse('food_of_the_day:detail', args=[self.meal.id]))
        self.assertTrue(res2.context['is_saved'])

    def test_saved_meal_in_profile_saved_collection(self):
        self.client.login(username='dineder', password='password123')
        SavedMeal.objects.create(user=self.user, meal=self.meal, recipe_title="Healthy Green Bowl")

        # Check 'meal' category
        res_meal = self.client.get(reverse('profile_saved'), {'category': 'meal'})
        self.assertEqual(res_meal.status_code, 200)
        self.assertContains(res_meal, "Healthy Green Bowl")

        # Check 'all' category
        res_all = self.client.get(reverse('profile_saved'), {'category': 'all'})
        self.assertEqual(res_all.status_code, 200)
        self.assertContains(res_all, "Healthy Green Bowl")

    def test_profile_saved_remove_meal(self):
        self.client.login(username='dineder', password='password123')
        saved = SavedMeal.objects.create(user=self.user, meal=self.meal, recipe_title="Healthy Green Bowl")

        # Remove via profile_saved_remove
        response = self.client.post(reverse('profile_saved_remove', args=['meal', saved.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SavedMeal.objects.filter(pk=saved.pk).exists())

    @patch('food_of_the_day.views.get_recipe')
    def test_toggle_save_meal_creates_snapshot(self, mock_get_recipe):
        mock_get_recipe.return_value = self.sample_recipe
        self.client.login(username='dineder', password='password123')

        response = self.client.post(
            reverse('food_of_the_day:toggle_save_meal', args=[self.meal.id]),
            {'recipe_title': 'Healthy Green Bowl'}
        )
        self.assertEqual(response.status_code, 302)
        saved = SavedMeal.objects.get(user=self.user, meal=self.meal)
        self.assertEqual(saved.recipe_id, self.meal.recipe_id)
        self.assertEqual(saved.recipe_title, 'Healthy Green Bowl')
        self.assertIsInstance(saved.snapshot_data, dict)
        self.assertEqual(saved.snapshot_data.get('title'), 'Healthy Green Bowl')
        self.assertEqual(saved.snapshot_data.get('calories'), 350)
        self.assertIn('1 cup spinach', saved.snapshot_data.get('ingredients', []))

    def test_saved_meal_persists_when_mealoftheday_deleted(self):
        saved = SavedMeal.objects.create(
            user=self.user,
            meal=self.meal,
            recipe_id=self.meal.recipe_id,
            recipe_title="Healthy Green Bowl",
            snapshot_data={'title': 'Healthy Green Bowl', 'calories': 350}
        )
        # Delete MealOfTheDay
        self.meal.delete()

        # SavedMeal must NOT be deleted (on_delete=models.SET_NULL)
        saved.refresh_from_db()
        self.assertIsNone(saved.meal)
        self.assertEqual(saved.recipe_title, "Healthy Green Bowl")
        self.assertEqual(saved.recipe_id, 716429)
        self.assertEqual(saved.snapshot_data.get('calories'), 350)

    @patch('food_of_the_day.views.get_recipe')
    def test_detail_view_snapshot_fallback(self, mock_get_recipe):
        from food_of_the_day.models import MealOfTheDay
        past_date = self.today - datetime.timedelta(days=1)
        meal = MealOfTheDay.objects.create(date=past_date, recipe_id=888888)

        # Create saved meal with snapshot
        SavedMeal.objects.create(
            user=self.user,
            meal=meal,
            recipe_id=888888,
            recipe_title="Fallback Snapshot Salad",
            snapshot_data={
                'id': 888888,
                'title': 'Fallback Snapshot Salad',
                'calories': 320,
                'servings': 2,
                'readyInMinutes': 15,
                'ingredients': ['1 head lettuce', 'Olive oil'],
                'instructions': ['Chop lettuce', 'Drizzle olive oil'],
                'sourceUrl': 'https://spoonacular.com',
            }
        )

        # Simulate Spoonacular being offline / returning None
        mock_get_recipe.return_value = None

        response = self.client.get(reverse('food_of_the_day:detail', args=[meal.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fallback Snapshot Salad")

    def test_build_recipe_snapshot_function(self):
        from food_of_the_day.services import build_recipe_snapshot
        snapshot = build_recipe_snapshot(self.sample_recipe)
        self.assertEqual(snapshot['title'], 'Healthy Green Bowl')
        self.assertEqual(snapshot['calories'], 350)
        self.assertEqual(snapshot['ready_in_minutes'], 30)
        self.assertEqual(snapshot['servings'], 2)
        self.assertEqual(len(snapshot['ingredients']), 1)
        self.assertEqual(len(snapshot['instructions']), 1)

    def test_build_recipe_snapshot_none_handling(self):
        from food_of_the_day.services import build_recipe_snapshot
        self.assertEqual(build_recipe_snapshot(None), {})
        self.assertEqual(build_recipe_snapshot('not a dict'), {})



class SeedMealsCommandTest(TestCase):
    def test_seed_meals_creates_entries(self):
        MealOfTheDay.objects.all().delete()
        call_command('seed_meals', days=10)
        self.assertEqual(MealOfTheDay.objects.count(), 10)

    def test_seed_meals_preserves_existing_entry(self):
        MealOfTheDay.objects.all().delete()
        today = datetime.date.today()
        MealOfTheDay.objects.create(date=today, recipe_id=999999)
        call_command('seed_meals', days=5)
        # 1 existing + 4 new
        self.assertEqual(MealOfTheDay.objects.count(), 5)
        self.assertEqual(MealOfTheDay.objects.get(date=today).recipe_id, 999999)

    def test_seed_meals_clear_flag(self):
        today = datetime.date.today()
        MealOfTheDay.objects.create(date=today, recipe_id=123)
        call_command('seed_meals', days=3, clear=True)
        self.assertEqual(MealOfTheDay.objects.count(), 3)


# change: the detail page shows a "Back to ..." link instead of the breadcrumb
class MealBackLinkTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='backlink', password='password123')
        self.meal = MealOfTheDay.objects.create(date=datetime.date.today(), recipe_id=716429)
        self.recipe = {"id": 716429, "title": "Healthy Green Bowl", "image": "", "readyInMinutes": 30, "servings": 2}

    @patch('food_of_the_day.views.get_recipe')
    def test_back_to_meal_of_the_day_by_default(self, mock_get_recipe):
        mock_get_recipe.return_value = self.recipe
        response = self.client.get(reverse('food_of_the_day:detail', args=[self.meal.id]))
        self.assertContains(response, 'Back to Meal of the Day')
        self.assertNotContains(response, 'Back to Saved')
        self.assertNotContains(response, '&rsaquo;')        # change: the old breadcrumb separator is gone

    @patch('food_of_the_day.views.get_recipe')
    def test_back_to_saved_when_opened_from_saved(self, mock_get_recipe):
        mock_get_recipe.return_value = self.recipe
        response = self.client.get(reverse('food_of_the_day:detail', args=[self.meal.id]), {'source': 'saved'})
        self.assertContains(response, 'Back to Saved')

    def test_saved_meal_opens_with_source_saved(self):
        SavedMeal.objects.create(user=self.user, meal=self.meal, recipe_title="Healthy Green Bowl")
        self.client.force_login(self.user)
        response = self.client.get(reverse('profile_saved'), {'category': 'meal'})
        self.assertContains(response, reverse('food_of_the_day:detail', args=[self.meal.id]) + '?source=saved')


# change: tests for the self-seeding helper, so a fresh PWS database still shows a meal
class GetTodaysMealTests(TestCase):
    # change: local imports keep this block self-contained at the bottom of the file
    from django.utils import timezone
    from food_of_the_day.constants import CURATED_RECIPE_IDS
    def test_creates_todays_meal_when_table_is_empty(self):
        from food_of_the_day.services import get_todays_meal
        self.assertEqual(MealOfTheDay.objects.count(), 0)
        meal = get_todays_meal()
        self.assertEqual(meal.date, self.timezone.localdate())
        self.assertIn(meal.recipe_id, self.CURATED_RECIPE_IDS)
        # change: calling it again must reuse the same row, not make a second one
        self.assertEqual(get_todays_meal().pk, meal.pk)
        self.assertEqual(MealOfTheDay.objects.count(), 1)

    def test_keeps_admin_pick_for_today(self):
        from food_of_the_day.services import get_todays_meal
        admin_pick = MealOfTheDay.objects.create(date=self.timezone.localdate(), recipe_id=999999)
        self.assertEqual(get_todays_meal().recipe_id, 999999)
        self.assertEqual(get_todays_meal().pk, admin_pick.pk)
