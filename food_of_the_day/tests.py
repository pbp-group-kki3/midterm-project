import datetime
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from django.db.utils import IntegrityError

from food_of_the_day.models import MealOfTheDay, MealComment
from food_of_the_day.services import (
    get_recipe,
    extract_calories,
    get_did_you_know,
    extract_ingredients,
    extract_instructions,
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
        # Top 2 should be Vitamin C (145.5% -> 146%) and Vitamin K (90%)
        self.assertIn("146% of your daily Vitamin C", facts[0])
        self.assertIn("90% of your daily Vitamin K", facts[1])

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

    @patch('food_of_the_day.services._fallback_get')
    def test_get_recipe_caching(self, mock_fallback_get):
        mock_fallback_get.return_value = self.sample_recipe

        # First call hits mock
        res1 = get_recipe(716429)
        self.assertEqual(res1['id'], 716429)
        mock_fallback_get.assert_called_once()

        # Second call returns from cache
        res2 = get_recipe(716429)
        self.assertEqual(res2['id'], 716429)
        mock_fallback_get.assert_called_once()  # Call count remains 1


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
        # Should prompt to log in and not reveal full preparation steps
        self.assertContains(response, "Log in to see the recipe")
        self.assertNotContains(response, "Preparation Steps")

    @patch('food_of_the_day.views.get_recipe')
    def test_detail_view_authenticated_user(self, mock_get_recipe):
        mock_get_recipe.return_value = self.sample_recipe
        self.client.login(username='dineder', password='password123')
        response = self.client.get(reverse('food_of_the_day:detail', args=[self.meal.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Preparation Steps")
        self.assertContains(response, "Mix everything in a bowl.")
        self.assertContains(response, "Ingredients")
        self.assertContains(response, "1 cup spinach")

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

    @patch('food_of_the_day.views.get_recipe')
    def test_slide_partial_view(self, mock_get_recipe):
        mock_get_recipe.return_value = self.sample_recipe
        response = self.client.get(reverse('food_of_the_day:slide_partial'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Healthy Green Bowl")
