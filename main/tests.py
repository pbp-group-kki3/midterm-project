from django.test import TestCase
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from main.models import FavoriteProduct, ViewHistory
from main.services.grading import spoonfeed_grade, grade_value, NUTRI_POINTS, GREEN_POINTS, NOVA_POINTS

# product constant
ULTRA_MILK = {
    "code": "8998009010637",
    "product_name": "Ultra Milk Low Fat",
    "nutriscore_grade": "b",
    "ecoscore_score": 37,
    "nova_group": 3,
    "categories_tags": ["en:dairies", "en:milks"],
}


# grading.py: pure Python, no API, no database
class GradingTests(TestCase):
    def test_all_three_scores(self):
        result = spoonfeed_grade(ULTRA_MILK)
        self.assertEqual(result["score"], 56.5)          # 75*0.5 + 37*0.35 + 40*0.15
        self.assertEqual(result["grade"], "C")

    def test_missing_nova_divides_by_remaining_weights(self):
        result = spoonfeed_grade({"nutriscore_grade": "b", "ecoscore_score": 37})
        self.assertEqual(result["score"], 59.4)          # (75*0.5 + 37*0.35) / 0.85
        self.assertNotIn("processing", result["parts"])

    def test_no_nutriscore_gives_question_mark(self):
        result = spoonfeed_grade({"ecoscore_score": 37, "nova_group": 3})
        self.assertEqual(result["grade"], "?")
        self.assertIsNone(result["score"])

    def test_grade_value(self):
        self.assertEqual(grade_value("B", NUTRI_POINTS), "B")
        self.assertEqual(grade_value("a-plus", GREEN_POINTS), "A+")
        self.assertEqual(grade_value(4, NOVA_POINTS), "4")
        self.assertEqual(grade_value("unknown", GREEN_POINTS), "?")
        self.assertEqual(grade_value(None, NUTRI_POINTS), "?")


# The Discover page. search_products is replaced by a fake, so no real API call happens
class ShowMainTests(TestCase):
    @patch("main.views.search_products")
    def test_first_visit_does_not_call_the_api(self, fake_search):
        response = self.client.get(reverse("main:show_main"))
        self.assertEqual(response.status_code, 200)
        fake_search.assert_not_called()                  # nothing typed, so no API call
        self.assertFalse(response.context["searched"])

    @patch("main.views.search_products", return_value=[dict(ULTRA_MILK)])
    def test_search_shows_graded_products(self, fake_search):
        response = self.client.get(reverse("main:show_main"), {"q": "susu uht"})
        products = response.context["products"]
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["spoonfeed"]["grade"], "C")
        self.assertEqual(products[0]["tiles"]["nova"], "3")

    @patch("main.views.search_products", return_value=None)
    def test_api_failure_sets_error(self, fake_search):
        response = self.client.get(reverse("main:show_main"), {"q": "susu uht"})
        self.assertTrue(response.context["error"])

    @patch("main.views.search_products", return_value=[])
    def test_no_results(self, fake_search):
        response = self.client.get(reverse("main:show_main"), {"q": "xyzqwe"})
        self.assertTrue(response.context["searched"])
        self.assertEqual(response.context["products"], [])


# Favorites and view history: need a logged-in user
class FavoriteAndHistoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="test-pass-123")
        self.url = reverse("main:toggle_favorite", args=[ULTRA_MILK["code"]])

    def test_logged_out_user_is_sent_to_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)      # redirect
        self.assertIn("/profiles/login/", response.url)  # LOGIN_URL from settings
        self.assertEqual(FavoriteProduct.objects.count(), 0)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)      # require_POST

    def test_toggle_adds_then_removes(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {"product_name": "Ultra Milk Low Fat"})
        self.assertEqual(FavoriteProduct.objects.filter(user=self.user).count(), 1)
        self.client.post(self.url)
        self.assertEqual(FavoriteProduct.objects.filter(user=self.user).count(), 0)

    @patch("main.views.get_alternatives", return_value=[])
    @patch("main.views.get_product", return_value=dict(ULTRA_MILK))
    def test_detail_page_saves_history_once(self, fake_product, fake_alternatives):
        self.client.force_login(self.user)
        url = reverse("main:product_detail", args=[ULTRA_MILK["code"]])
        self.client.get(url)
        self.client.get(url)                             # same product twice
        self.assertEqual(ViewHistory.objects.filter(user=self.user).count(), 1)

    @patch("main.views.get_product", return_value=None)
    def test_detail_page_when_api_fails(self, fake_product):
        response = self.client.get(reverse("main:product_detail", args=["000"]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["product"])