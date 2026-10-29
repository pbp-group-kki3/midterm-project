import datetime
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from django.core.management import call_command
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError

from food_of_the_day.models import MealOfTheDay, MealComment
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

    @patch('food_of_the_day.views.get_recipe')
    def test_slide_partial_view(self, mock_get_recipe):
        mock_get_recipe.return_value = self.sample_recipe
        response = self.client.get(reverse('food_of_the_day:slide_partial'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Healthy Green Bowl")


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

