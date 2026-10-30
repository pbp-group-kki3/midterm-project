from django.test import TestCase
from unittest.mock import patch, MagicMock   # change: MagicMock builds fake API responses for the openfoodfacts tests
import requests                              # change: needed to fake a network error (requests.RequestException)
from django.core.cache import cache          # change: the API tests empty the cache first so one test can't leak into another

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from main.models import FavoriteProduct, ViewHistory
from main.services.filters import passes_filters, preference_fit
from main.views import prepare_card
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

    def test_grade_value(self):
        self.assertEqual(grade_value("B", NUTRI_POINTS), "B")
        self.assertEqual(grade_value("a-plus", GREEN_POINTS), "A+")
        self.assertEqual(grade_value(4, NOVA_POINTS), "4")
        self.assertEqual(grade_value("unknown", GREEN_POINTS), "?")
        self.assertEqual(grade_value(None, NUTRI_POINTS), "?")

    # change: Alyssa's grading fix grades a product from whatever scores it has,
    # so a missing Nutri-Score no longer means "?". This test now checks that new rule
    def test_no_nutriscore_uses_the_other_two(self):
        result = spoonfeed_grade({"ecoscore_score": 37, "nova_group": 3})
        self.assertEqual(result["score"], 37.9)          # (37*0.35 + 40*0.15) / 0.50
        self.assertEqual(result["grade"], "D")
        self.assertNotIn("nutrition", result["parts"])


    # change: "?" only shows up now when all three scores are missing
    def test_no_scores_at_all_gives_question_mark(self):
        result = spoonfeed_grade({"product_name": "Mystery snack"})
        self.assertEqual(result["grade"], "?")
        self.assertIsNone(result["score"])

# The Discover page. search_products is replaced by a fake, so no real API call happens
class ShowMainTests(TestCase):
    @patch("main.views.browse_products", return_value=[dict(ULTRA_MILK)])
    @patch("main.views.search_products")
    def test_first_visit_shows_popular_products(self, fake_search, fake_browse):
        response = self.client.get(reverse("main:show_main"))
        self.assertEqual(response.status_code, 200)
        fake_search.assert_not_called()                  # nothing typed: no search...
        fake_browse.assert_called_once()                 # ...popular products instead
        self.assertFalse(response.context["searched"])
        self.assertEqual(len(response.context["products"]), 1)

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
        self.assertIn(reverse("login"), response.url)     # the Profile module's login page
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

# Filters (filters.py) and the filtered search page
class FilterTests(TestCase):
    def setUp(self):
        # two real-looking products: one halal NOVA 3 milk, one NOVA 4 product that contains milk
        self.halal = prepare_card(dict(ULTRA_MILK, labels_tags=["en:halal"], allergens_tags=[]))
        self.ultra = prepare_card({
            "code": "111", "product_name": "Choco drink", "nutriscore_grade": "d",
            "nova_group": 4, "labels_tags": [], "allergens_tags": ["en:milk"],
        })

    def test_halal_filter(self):
        self.assertTrue(passes_filters(self.halal, [], ["halal"], "any", []))
        self.assertFalse(passes_filters(self.ultra, [], ["halal"], "any", []))

    def test_not_ultra_processed(self):
        self.assertTrue(passes_filters(self.halal, [], [], "not_ultra", []))    # NOVA 3
        self.assertFalse(passes_filters(self.ultra, [], [], "not_ultra", []))   # NOVA 4

    def test_avoid_allergen(self):
        self.assertFalse(passes_filters(self.ultra, [], [], "any", ["milk"]))  # lists milk
        self.assertTrue(passes_filters(self.halal, [], [], "any", ["milk"]))   # empty list = unknown, kept

    def test_grade_filter(self):
        self.assertTrue(passes_filters(self.halal, ["C"], [], "any", []))
        self.assertFalse(passes_filters(self.halal, ["A", "B"], [], "any", []))

    def test_card_tags(self):
        self.assertEqual(self.halal["tags"][0]["text"], "Halal")
        self.assertEqual(self.ultra["tags"], [])

    @patch("main.views.search_products")
    def test_page_filters_the_search_results(self, fake_search):
        fake_search.return_value = [dict(self.halal), dict(self.ultra)]
        response = self.client.get(reverse("main:show_main"), {"q": "susu", "label": "halal"})
        names = [p["product_name"] for p in response.context["products"]]
        self.assertEqual(names, ["Ultra Milk Low Fat"])
        self.assertEqual(response.context["filter_count"], 1)

    @patch("main.views.search_products")
    def test_load_more_shows_six_then_twelve(self, fake_search):
        fake_search.return_value = [dict(ULTRA_MILK, code=str(i)) for i in range(10)]
        first = self.client.get(reverse("main:show_main"), {"q": "susu"})
        self.assertEqual(len(first.context["products"]), 6)
        self.assertTrue(first.context["has_more"])
        more = self.client.get(reverse("main:show_main"), {"q": "susu", "show": 12})
        self.assertEqual(len(more.context["products"]), 10)
        self.assertFalse(more.context["has_more"])


# The backup search is used when the normal search fails (e.g. Open Food Facts 503)
class BackupSearchTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()                                    # start every test with an empty cache

    @patch("main.services.openfoodfacts.backup_search", return_value=[dict(ULTRA_MILK)])
    @patch("main.services.openfoodfacts.requests.get")
    def test_search_falls_back_when_api_fails(self, fake_get, fake_backup):
        import requests
        from main.services.openfoodfacts import search_products
        fake_get.side_effect = requests.RequestException("503")   # the normal search fails
        results = search_products("susu uht")
        self.assertEqual(results[0]["product_name"], "Ultra Milk Low Fat")
        fake_backup.assert_called_once()

    @patch("main.services.openfoodfacts.backup_search", return_value=None)
    @patch("main.services.openfoodfacts.requests.get")
    def test_search_returns_none_when_both_fail(self, fake_get, fake_backup):
        import requests
        from main.services.openfoodfacts import search_products
        fake_get.side_effect = requests.RequestException("503")
        self.assertIsNone(search_products("susu uht"))


# Compare tray: + Compare saves barcodes in request.session["compare"] (read by Alyssa's page), max 3
class CompareTrayTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="test-pass-123")
        self.client.force_login(self.user)

    def add(self, code):
        url = reverse("main:add_to_compare", args=[code])
        return self.client.post(url, {"product_name": f"Milk {code}", "grade": "C", "next": "/"})

    def test_logged_out_goes_to_login(self):
        self.client.logout()
        response = self.client.post(reverse("main:add_to_compare", args=["1"]))
        self.assertIn(reverse("login"), response.url)

    def test_add_saves_barcode_in_session(self):
        self.add("1")
        self.assertEqual(self.client.session["compare"], ["1"])

    def test_no_duplicates_and_max_three(self):
        for code in ["1", "1", "2", "3", "4"]:
            self.add(code)
        self.assertEqual(self.client.session["compare"], ["1", "2", "3"])   # "1" once, "4" refused

    def test_remove(self):
        self.add("1")
        self.add("2")
        self.client.post(reverse("main:remove_from_compare", args=["1"]), {"next": "/"})
        self.assertEqual(self.client.session["compare"], ["2"])

    @patch("main.views.browse_products", return_value=[])
    def test_tray_on_the_page(self, fake_browse):
        self.add("1")
        response = self.client.get(reverse("main:show_main"))
        self.assertEqual(response.context["compare_count"], 1)
        self.assertFalse(response.context["can_compare"])        # needs 2
        self.assertContains(response, "1 of 3 selected")
        self.add("2")
        response = self.client.get(reverse("main:show_main"))
        self.assertTrue(response.context["can_compare"])
        self.assertContains(response, 'href="/compare/"')                     # "Compare now" -> Alyssa's page


# "Fits your preferences": only "fits" when the data confirms it
class PreferenceFitTests(TestCase):
    HALAL_MILK = {"labels_tags": ["en:halal"], "allergens_tags": ["en:milk"],
                  "ingredients_analysis_tags": ["en:non-vegan", "en:vegetarian"]}

    def test_no_preferences_no_chip(self):
        self.assertIsNone(preference_fit(self.HALAL_MILK, None))                          # logged out
        self.assertIsNone(preference_fit(self.HALAL_MILK, {"diet": "none", "off_tags": []}))

    def test_fits(self):
        fit = preference_fit(self.HALAL_MILK, {"diet": "halal", "off_tags": []})
        self.assertEqual(fit["status"], "fits")

    def test_allergen_conflict(self):
        fit = preference_fit(self.HALAL_MILK, {"diet": "halal", "off_tags": ["en:milk"]})
        self.assertEqual(fit, {"status": "conflict", "text": "Contains milk"})

    def test_not_vegan(self):
        fit = preference_fit(self.HALAL_MILK, {"diet": "vegan", "off_tags": []})
        self.assertEqual(fit["status"], "conflict")

    def test_missing_data_is_unknown(self):
        fit = preference_fit({"labels_tags": []}, {"diet": "halal", "off_tags": []})
        self.assertEqual(fit["text"], "? Can't verify halal")

    def test_list_diets(self):
        self.assertIsNone(preference_fit(self.HALAL_MILK, {"diet": [], "off_tags": []}))
        self.assertEqual(preference_fit(self.HALAL_MILK, {"diet": ["halal"], "off_tags": []})["status"],"fits")
        self.assertEqual(preference_fit(self.HALAL_MILK,{"diet": ["halal", "vegan"], "off_tags": []}),{"status": "conflict", "text": "Not vegan"})


# Detail page panels (details.py), checked with the real Open Food Facts data of Ultra Milk Low Fat
class DetailPanelTests(TestCase):
    def setUp(self):
        from main.views import prepare_card
        self.product = prepare_card(dict(
            ULTRA_MILK,
            ecoscore_grade="d",
            nutriments={"energy-kcal_100g": 44, "fat_100g": 1.2, "salt_100g": 0.125},
            nutrient_levels={"fat": "low", "salt": "low", "saturated-fat": "low", "sugars": "low"},
            allergens_tags=["en:milk"],
            ingredients_analysis_tags=["en:palm-oil-free", "en:non-vegan"],
            ecoscore_data={
                "agribalyse": {"co2_total": 1.306214873},
                "adjustments": {
                    "packaging": {"warning": "packaging_data_missing"},
                    "origins_of_ingredients": {"aggregated_origins": [{"origin": "en:unknown", "percent": 100}]},
                },
            },
        ))

    def test_bar_colors_follow_the_figma(self):
        from main.services.details import build_grade_rows
        tones = [row["tone"] for row in build_grade_rows(self.product)]
        self.assertEqual(tones, ["success", "danger", "warning"])     # 75 green, 37 red, 40 amber

    def test_green_dots_and_values(self):
        from main.services.details import build_nutrition
        rows = {row["label"]: row for row in build_nutrition(self.product)}
        self.assertTrue(rows["Fat"]["good"])
        self.assertFalse(rows["Energy"]["good"])                       # energy has no level
        self.assertEqual(rows["Energy"]["value"], "44 kcal")
        self.assertEqual(rows["Salt"]["value"], "0.125 g")
        self.assertEqual(rows["Fiber"]["value"], "?")                  # missing

    def test_ingredient_badges(self):
        from main.services.details import build_ingredient_badges
        texts = [b["text"] for b in build_ingredient_badges(self.product)]
        self.assertEqual(texts, ["Contains milk", "Non-vegan", "Palm oil free"])

    def test_environment_rows(self):
        from main.services.details import build_environment
        rows = {row["label"]: row["value"] for row in build_environment(self.product)}
        self.assertEqual(rows["Green-Score"], "D, 37 out of 100")
        self.assertEqual(rows["Carbon footprint"], "131 g CO\u2082e per 100 g")
        self.assertEqual(rows["Packaging"], "Not indicated")
        self.assertEqual(rows["Origin of ingredients"], "Not indicated")


# Heart without page reload, red when saved, and small detail fixes
class FavoriteDisplayTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="test-pass-123")
        self.client.force_login(self.user)
        self.url = reverse("main:toggle_favorite", args=[ULTRA_MILK["code"]])

    def test_click_with_javascript_answers_json(self):
        ajax = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        first = self.client.post(self.url, {"product_name": "Ultra Milk Low Fat"}, **ajax)
        self.assertEqual(first.json(), {"saved": True})        # no redirect, so no jump to the top
        second = self.client.post(self.url, **ajax)
        self.assertEqual(second.json(), {"saved": False})

    @patch("main.views.search_products")
    def test_saved_product_has_red_heart(self, fake_search):
        FavoriteProduct.objects.create(user=self.user, barcode=ULTRA_MILK["code"], product_name="Ultra Milk Low Fat")
        fake_search.return_value = [dict(ULTRA_MILK), dict(ULTRA_MILK, code="999")]
        response = self.client.get(reverse("main:show_main"), {"q": "susu"})
        flags = [p["is_favorite"] for p in response.context["products"]]
        self.assertEqual(flags, [True, False])
        self.assertContains(response, "is-active")              # shared class: red heart

    def test_unknown_packaging_is_not_indicated(self):
        from main.services.details import build_environment
        product = {"ecoscore_data": {"adjustments": {"packaging": {"packagings": [{"material": "en:unknown"}]}}}}
        rows = {row["label"]: row["value"] for row in build_environment(product)}
        self.assertEqual(rows["Packaging"], "Not indicated")

    def test_ingredient_underscores_removed(self):
        from main.services.details import clean_ingredients
        self.assertEqual(clean_ingredients({"ingredients_text": "Wholegrain _Oat_ Flakes"}), "Wholegrain Oat Flakes")


# change: the card button states from the Figma frames "2 product in compare" and "Return with 3 Products"
class CompareButtonStateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="test-pass-123")
        self.client.force_login(self.user)

    def add(self, code, grade="C"):
        self.client.post(reverse("main:add_to_compare", args=[code]),
                         {"product_name": f"Milk {code}", "grade": grade, "next": "/"})

    @patch("main.views.search_products")
    def test_added_and_compare(self, fake_search):
        fake_search.return_value = [dict(ULTRA_MILK, code="1"), dict(ULTRA_MILK, code="2")]
        self.add("1")
        page = self.client.get(reverse("main:show_main"), {"q": "susu"}).content.decode()
        self.assertIn("✓ Added", page)          # product 1 is in the tray
        self.assertIn("+ Compare", page)        # product 2 isn't

    @patch("main.views.search_products")
    def test_full_tray_shows_limit_reached(self, fake_search):
        fake_search.return_value = [dict(ULTRA_MILK, code=c) for c in ["1", "2", "3", "4"]]
        for code in ["1", "2", "3"]:
            self.add(code)
        page = self.client.get(reverse("main:show_main"), {"q": "susu"}).content.decode()
        self.assertIn("Limit reached", page)    # product 4 can't be added
        self.assertNotIn("✓ Added", page)       # full tray: the added ones just say "Added", greyed out
        self.assertNotIn("+ Compare", page)

    def test_added_button_takes_it_out_again(self):
        self.add("1")
        self.client.post(reverse("main:remove_from_compare", args=["1"]), {"next": "/"})
        self.assertEqual(self.client.session["compare"], [])

    @patch("main.views.browse_products", return_value=[])
    def test_tray_tile_uses_grade_colour(self, fake_browse):
        self.add("1", grade="B")
        self.add("2", grade="?")
        page = self.client.get(reverse("main:show_main")).content.decode()
        self.assertIn("discover-tray-grade grade-b", page)               # shared green for B
        self.assertIn("discover-tray-grade discover-tray-grade-unknown", page)   # grey only for "?"


# change: compare without reloading. JavaScript gets back the new tray and the new buttons as HTML
class CompareNoReloadTests(TestCase):
    AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="test-pass-123")
        self.client.force_login(self.user)

    def post(self, view, code, slots):
        import json
        return self.client.post(reverse(view, args=[code]), {
            "product_name": f"Milk {code}", "grade": "C", "next": "/",
            "slots": json.dumps(slots),
        }, **self.AJAX)

    def test_add_returns_tray_and_buttons(self):
        slots = [{"code": "1", "name": "Milk 1", "grade": "C", "style": "btn-outline"},
                 {"code": "2", "name": "Milk 2", "grade": "B", "style": "btn-outline"}]
        data = self.post("main:add_to_compare", "1", slots).json()
        self.assertIn("1 of 3 selected", data["tray"])           # new tray HTML
        self.assertIn("✓ Added", data["buttons"]["1"])           # the clicked card
        self.assertIn("+ Compare", data["buttons"]["2"])         # the other card
        self.assertEqual(self.client.session["compare"], ["1"])

    def test_third_product_turns_others_into_limit_reached(self):
        slots = [{"code": c, "name": c, "grade": "C", "style": "btn-outline"} for c in ["1", "2", "3", "4"]]
        for code in ["1", "2"]:
            self.post("main:add_to_compare", code, slots)
        data = self.post("main:add_to_compare", "3", slots).json()
        self.assertIn("Limit reached", data["buttons"]["4"])
        self.assertIn("is-full", data["tray"])

    def test_remove_returns_json_too(self):
        self.post("main:add_to_compare", "1", [])
        data = self.post("main:remove_from_compare", "1", []).json()
        self.assertEqual(data["tray"].strip(), "")                # empty tray: nothing to show
        self.assertEqual(self.client.session["compare"], [])

    def test_bad_slots_dont_crash(self):
        response = self.client.post(reverse("main:add_to_compare", args=["1"]),
                                    {"slots": "not json"}, **self.AJAX)
        self.assertEqual(response.json()["buttons"], {})


# change: "Load more products" without reloading: JavaScript gets only the next cards
class LoadMoreNoReloadTests(TestCase):
    @patch("main.views.search_products")
    def test_next_cards_as_json(self, fake_search):
        fake_search.return_value = [dict(ULTRA_MILK, code=str(i), product_name=f"Milk {i}") for i in range(10)]
        data = self.client.get(reverse("main:show_main"), {"q": "susu", "show": 12},
                               HTTP_X_REQUESTED_WITH="XMLHttpRequest").json()
        self.assertIn("Milk 6", data["cards"])           # card 7 (index 6) is new
        self.assertIn("Milk 9", data["cards"])
        self.assertNotIn("Milk 5", data["cards"])        # the first 6 are already on the page
        self.assertFalse(data["has_more"])               # 10 products, 12 asked: nothing left

    @patch("main.views.search_products")
    def test_more_url_for_next_click(self, fake_search):
        fake_search.return_value = [dict(ULTRA_MILK, code=str(i)) for i in range(20)]
        data = self.client.get(reverse("main:show_main"), {"q": "susu", "show": 12},
                               HTTP_X_REQUESTED_WITH="XMLHttpRequest").json()
        self.assertTrue(data["has_more"])
        self.assertIn("show=18", data["more_url"])

class ProductOverlayAndTrayTests(TestCase):
    def setUp(self):
        from copy import deepcopy

        self.user = get_user_model().objects.create_user(
            username="overlay-tray-tester",
            password="overlay-tray-test-password",
        )

        self.codes = [
            "1111111111111",
            "2222222222222",
            "3333333333333",
        ]

        self.products = {
            code: {
                "code": code,
                "product_name": f"Test product {index}",
                "brands": "Test brand",
                "quantity": "250 ml",
                "image_front_small_url": (
                    "https://example.com/product.jpg"
                ),
                "nutriscore_grade": "b",
                "ecoscore_grade": "c",
                "ecoscore_score": 50,
                "nova_group": 3,
                "categories_tags": ["en:milks"],
                "labels_tags": [],
                "allergens_tags": ["en:milk"],
                "ingredients_text": "Milk and test ingredients.",
                "nutriments": {
                    "energy-kcal_100g": 44,
                    "fat_100g": 1.2,
                    "salt_100g": 0.1,
                },
            }
            for index, code in enumerate(self.codes, start=1)
        }

        self.get_product = self.enterContext(
            patch("main.views.get_product")
        )
        self.get_product.side_effect = (
            lambda barcode: deepcopy(
                self.products.get(barcode)
            )
        )

        self.alternatives = self.enterContext(
            patch(
                "main.views.get_alternatives",
                return_value=[
                    deepcopy(self.products[self.codes[1]])
                ],
            )
        )

        self.enterContext(
            patch(
                "main.views.browse_products",
                return_value=[],
            )
        )
        self.enterContext(
            patch(
                "main.views.get_preferences",
                return_value=None,
            )
        )

        self.client.force_login(self.user)

        session = self.client.session
        session["compare"] = self.codes[:2]
        session["compare_info"] = {
            code: {
                "name": self.products[code]["product_name"],
                "grade": "C",
            }
            for code in self.codes[:2]
        }
        session.save()

    def detail_url(self, code=None):
        return reverse(
            "main:product_detail",
            args=[code or self.codes[0]],
        )

    def fragment(self, code=None, client=None):
        return (client or self.client).get(
            self.detail_url(code),
            {"fragment": "1", "source": "comparison"},
            HTTP_ACCEPT="application/json",
        )

    def test_fragment_matches_each_requested_product(self):
        for code in self.codes:
            response = self.fragment(code)

            self.assertEqual(response.status_code, 200)
            data = response.json()

            self.assertEqual(data["barcode"], code)
            self.assertIn(
                f'data-product-barcode="{code}"',
                data["html"],
            )
            self.assertIn(
                self.products[code]["product_name"],
                data["html"],
            )

    def test_fragment_has_details_without_shell_or_recommendations(self):
        response = self.fragment()
        html = response.json()["html"]

        for text in [
            "How the grade is built",
            "Nutrition per",
            "Ingredients and allergens",
            "Environment",
            "Source: Open Food Facts",
        ]:
            self.assertIn(text, html)

        for text in [
            "<html",
            "<script",
            'class="site-header"',
            'class="site-footer"',
            'id="compare-tray-holder"',
            "Back to Discover",
            "Back to Compare",
            "Recommendations",
            "Comparison selections are locked while viewing details.",
            "js-compare-form",
        ]:
            self.assertNotIn(text, html)

        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertIn(
            f'id="product-detail-heading-{self.codes[0]}"',
            html,
        )
        self.assertIn(
            "no-store",
            response.headers["Cache-Control"],
        )
        self.alternatives.assert_not_called()

    def test_fragment_preserves_lineup_and_does_not_write_history(self):
        before = list(self.client.session["compare"])
        before_info = dict(
            self.client.session["compare_info"]
        )

        self.fragment()
        self.fragment(self.codes[1])

        self.assertEqual(
            self.client.session["compare"],
            before,
        )
        self.assertEqual(
            self.client.session["compare_info"],
            before_info,
        )
        self.assertFalse(
            ViewHistory.objects.filter(
                user=self.user
            ).exists()
        )

    def test_unavailable_fragment_returns_retryable_error(self):
        # change: a real-looking barcode that isn't in the fake data (= the API can't load it).
        # "unknown-product" now gets 404, because barcodes must be digits (step 1, input safety)
        response = self.fragment("9999999999999")

        self.assertEqual(response.status_code, 503)
        self.assertIn("message", response.json())
        self.assertNotIn("html", response.json())

    def test_fragment_rejects_post(self):
        response = self.client.post(
            f"{self.detail_url()}?fragment=1"
        )

        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            response.headers["Allow"],
            "GET",
        )

    def test_standalone_has_no_tray_and_preserves_selection(self):
        before = list(self.client.session["compare"])

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "main/product_detail.html",
        )
        self.assertTemplateUsed(
            response,
            "main/components/product_detail_content.html",
        )

        self.assertContains(response, "Back to Discover")
        self.assertContains(response, "Recommendations")
        self.assertNotContains(
            response,
            'id="compare-tray-holder"',
        )
        self.assertNotContains(
            response,
            'class="discover-tray',
        )

        self.assertEqual(
            self.client.session["compare"],
            before,
        )
        self.assertTrue(
            ViewHistory.objects.filter(
                user=self.user,
                barcode=self.codes[0],
            ).exists()
        )

    def test_returning_to_discover_renders_preserved_tray(self):
        self.client.get(self.detail_url())

        response = self.client.get(
            reverse("main:show_main")
        )

        self.assertContains(
            response,
            'id="compare-tray-holder"',
        )
        self.assertContains(response, "2 of 3 selected")

        for code in self.codes[:2]:
            self.assertContains(
                response,
                self.products[code]["product_name"],
            )

        self.assertEqual(
            self.client.session["compare"],
            self.codes[:2],
        )

    def test_standalone_compare_action_updates_session_without_tray(self):
        third = self.codes[2]

        response = self.client.post(
            reverse(
                "main:add_to_compare",
                args=[third],
            ),
            {
                "product_name": self.products[third]["product_name"],
                "grade": "C",
                "next": self.detail_url(third),
                "slots": (
                    '[{"code":"3333333333333",'
                    '"name":"Test product 3",'
                    '"grade":"C","style":"btn-primary"}]'
                ),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.session["compare"],
            self.codes,
        )
        self.assertIn("Added", response.json()["buttons"][third])

        detail = self.client.get(self.detail_url(third))
        self.assertNotContains(
            detail,
            'id="compare-tray-holder"',
        )

        discover = self.client.get(
            reverse("main:show_main")
        )
        self.assertContains(discover, "3 of 3 selected")

    def test_discover_ajax_response_still_supplies_tray(self):
        response = self.client.post(
            reverse(
                "main:remove_from_compare",
                args=[self.codes[1]],
            ),
            {"slots": "[]"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "1 of 3 selected",
            response.json()["tray"],
        )
        self.assertEqual(
            self.client.session["compare"],
            [self.codes[0]],
        )

    def test_favorite_action_preserves_lineup(self):
        before = list(self.client.session["compare"])

        response = self.client.post(
            reverse(
                "main:toggle_favorite",
                args=[self.codes[0]],
            ),
            {"product_name": "Test product 1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["saved"])
        self.assertEqual(
            self.client.session["compare"],
            before,
        )

    def test_favorite_still_requires_authentication(self):
        self.client.logout()

        response = self.client.post(
            reverse(
                "main:toggle_favorite",
                args=[self.codes[0]],
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        # change: a JavaScript click now gets 401 + JSON (login_required_json, step 2) instead of a 302 redirect.
        # main.js then opens the login page. Still not saved without logging in
        self.assertEqual(response.status_code, 401)
        self.assertFalse(
            FavoriteProduct.objects.exists()
        )

    def test_favorite_still_requires_csrf(self):
        from django.test import Client

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        self.fragment(client=csrf_client)

        response = csrf_client.post(
            reverse(
                "main:toggle_favorite",
                args=[self.codes[0]],
            ),
            {"product_name": "Test product 1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            FavoriteProduct.objects.exists()
        )

    def test_fragment_ids_are_unique(self):
        from html.parser import HTMLParser

        class IDCollector(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = []

            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)

                if "id" in attributes:
                    self.ids.append(attributes["id"])

        parser = IDCollector()
        parser.feed(self.fragment().json()["html"])

        self.assertEqual(
            len(parser.ids),
            len(set(parser.ids)),
        )


# change: the profile now saves diet as a list, e.g. ["vegan"] or ["halal", "vegan"]
class PreferenceListTests(TestCase):
    def test_diet_as_list(self):
        vegan = {"ingredients_analysis_tags": ["en:vegan"], "allergens_tags": []}
        fit = preference_fit(vegan, {"diet": ["vegan"], "off_tags": []})
        self.assertEqual(fit["status"], "fits")

    def test_two_diets_one_unknown(self):
        vegan_only = {"ingredients_analysis_tags": ["en:vegan"], "labels_tags": [], "allergens_tags": []}
        fit = preference_fit(vegan_only, {"diet": ["vegan", "halal"], "off_tags": []})
        self.assertEqual(fit["text"], "? Can't verify halal")      # vegan ok, halal not on the label

    def test_empty_list_means_no_chip(self):
        self.assertIsNone(preference_fit({}, {"diet": [], "off_tags": []}))

# change: openfoodfacts.py was only at 28% because every other test fakes the whole file.
# Here we fake one level lower instead: requests.get. So the real code in openfoodfacts.py runs
# (caching, backup search, alternatives), but no test ever calls the real API (fast, works offline)
from main.services import openfoodfacts as off   # change: short name, so the tests below stay readable

API_DOWN = requests.RequestException("503 too busy")   # change: what requests raises when the server fails


def fake_response(data):
    # change: a pretend HTTP answer. .json() gives our data, raise_for_status() does nothing (= status 200)
    response = MagicMock()
    response.json.return_value = data
    return response


@patch("main.services.openfoodfacts.requests.get")   # change: every test in this class gets the fake as fake_get
class OpenFoodFactsTests(TestCase):
    def setUp(self):
        cache.clear()   # change: start every test with an empty cache, otherwise results from the last test would be reused

    # --- get_product ---
    def test_product_is_fetched_once_then_cached(self, fake_get):
        fake_get.return_value = fake_response({"product": ULTRA_MILK})
        first = off.get_product("8998009010637")
        second = off.get_product("8998009010637")       # change: same barcode again -> should come from the cache
        self.assertEqual(first, ULTRA_MILK)
        self.assertEqual(second, ULTRA_MILK)
        self.assertEqual(fake_get.call_count, 1)         # change: only ONE real request for two calls

    def test_product_is_none_when_api_is_down(self, fake_get):
        fake_get.side_effect = API_DOWN                  # change: side_effect = raise this instead of returning
        self.assertIsNone(off.get_product("000"))

    # --- search_products + backup_search ---
    def test_search_cleans_the_text_and_caches(self, fake_get):
        fake_get.return_value = fake_response({"products": [ULTRA_MILK]})
        self.assertEqual(off.search_products("  SUSU "), [ULTRA_MILK])
        off.search_products("susu")                      # change: same search after cleaning -> cache hit
        self.assertEqual(fake_get.call_count, 1)
        self.assertEqual(fake_get.call_args.kwargs["params"]["search_terms"], "susu")

    def test_search_uses_the_backup_when_the_main_api_fails(self, fake_get):
        # change: 1st call (main API) fails, 2nd call (backup service) answers with "hits"
        fake_get.side_effect = [API_DOWN, fake_response({"hits": [ULTRA_MILK]})]
        self.assertEqual(off.search_products("susu"), [ULTRA_MILK])
        self.assertEqual(fake_get.call_args.args[0], off.BACKUP_SEARCH_URL)   # change: last call went to the backup

    def test_search_is_none_when_both_fail(self, fake_get):
        fake_get.side_effect = API_DOWN                  # change: every call fails, main and backup
        self.assertIsNone(off.search_products("susu"))

    # --- browse_products ---
    def test_browse_asks_for_popular_products_and_caches(self, fake_get):
        fake_get.return_value = fake_response({"products": [ULTRA_MILK]})
        self.assertEqual(off.browse_products(), [ULTRA_MILK])
        off.browse_products()
        self.assertEqual(fake_get.call_count, 1)
        self.assertEqual(fake_get.call_args.kwargs["params"]["sort_by"], "unique_scans_n")

    def test_browse_backup_keeps_the_popular_sort(self, fake_get):
        fake_get.side_effect = [API_DOWN, fake_response({"hits": [ULTRA_MILK]})]
        self.assertEqual(off.browse_products(), [ULTRA_MILK])
        self.assertEqual(fake_get.call_args.kwargs["params"]["sort_by"], "-unique_scans_n")

    def test_browse_is_none_when_both_fail(self, fake_get):
        fake_get.side_effect = API_DOWN
        self.assertIsNone(off.browse_products())

    # --- get_alternatives ---
    # change: ULTRA_MILK is grade C (56.5). Only products with a BETTER grade should come back, best first
    GRADE_A = {"code": "1", "nutriscore_grade": "a", "ecoscore_score": 90, "nova_group": 1}   # 96.5 -> A
    GRADE_B = {"code": "2", "nutriscore_grade": "b", "ecoscore_score": 70, "nova_group": 2}   # 73.25 -> B
    GRADE_E = {"code": "3", "nutriscore_grade": "e", "nova_group": 4}                          # 0 -> E
    NO_GRADE = {"code": "4", "product_name": "No data"}                                       # "?"

    def test_alternatives_are_better_graded_and_best_first(self, fake_get):
        candidates = [dict(ULTRA_MILK), dict(self.GRADE_B), dict(self.GRADE_E), dict(self.NO_GRADE), dict(self.GRADE_A)]
        fake_get.return_value = fake_response({"products": candidates})
        result = off.get_alternatives(dict(ULTRA_MILK))
        self.assertEqual([p["code"] for p in result], ["1", "2"])   # change: itself, E and "?" are left out; A before B
        self.assertEqual(result[0]["spoonfeed"]["grade"], "A")
        off.get_alternatives(dict(ULTRA_MILK))                       # change: same category -> cached
        self.assertEqual(fake_get.call_count, 1)

    def test_no_categories_means_no_alternatives(self, fake_get):
        self.assertEqual(off.get_alternatives({"code": "9"}), [])
        fake_get.assert_not_called()                                 # change: it shouldn't even ask the API

    def test_ungraded_product_gets_no_alternatives(self, fake_get):
        self.assertEqual(off.get_alternatives({"code": "9", "categories_tags": ["en:milks"]}), [])
        fake_get.assert_not_called()

    def test_alternatives_use_the_backup_when_the_api_fails(self, fake_get):
        fake_get.side_effect = [API_DOWN, fake_response({"hits": [dict(self.GRADE_A)]})]
        self.assertEqual([p["code"] for p in off.get_alternatives(dict(ULTRA_MILK))], ["1"])

    def test_alternatives_are_empty_when_both_fail(self, fake_get):
        fake_get.side_effect = API_DOWN
        self.assertEqual(off.get_alternatives(dict(ULTRA_MILK)), [])


# change: the last small branches no test reached yet (edge cases the rubric's 3.5 asks for)
class EdgeCaseTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="edge", password="test-pass-123")

    # models.py: the names shown in Django admin
    def test_model_names_in_admin(self):
        named = FavoriteProduct.objects.create(user=self.user, barcode="1", product_name="Ultra Milk")
        unnamed = ViewHistory.objects.create(user=self.user, barcode="2")
        self.assertEqual(str(named), "edge - Ultra Milk")
        self.assertEqual(str(unnamed), "edge viewed 2")        # change: no name -> falls back to the barcode

    # grading.py: Green-Score letter without a number, and the A / B cut-offs
    def test_green_letter_only_and_top_grades(self):
        self.assertEqual(spoonfeed_grade({"ecoscore_grade": "a"})["grade"], "A")      # 85 -> A
        self.assertEqual(spoonfeed_grade({"nutriscore_grade": "b"})["grade"], "B")    # 75 -> B

    # details.py: per 100 ml / per 100 g, vegan + palm oil badges, Green-Score letter only
    def test_detail_page_small_cases(self):
        from main.services.details import nutrition_unit, build_ingredient_badges, build_environment
        self.assertEqual(nutrition_unit({"quantity": "1 L"}), "100 ml")
        self.assertEqual(nutrition_unit({"quantity": "250 g"}), "100 g")
        self.assertEqual(nutrition_unit({}), "100 g or ml")
        badges = [b["text"] for b in build_ingredient_badges({"ingredients_analysis_tags": ["en:vegan", "en:palm-oil"]})]
        self.assertEqual(badges, ["Vegan", "Contains palm oil"])
        rows = {row["label"]: row["value"] for row in build_environment({"ecoscore_grade": "b"})}
        self.assertEqual(rows["Green-Score"], "B")             # change: letter but no score number

    # filters.py: unknown label in the URL, sort key, and the two "can't verify" chips
    def test_filter_edge_cases(self):
        from main.services.filters import best_grade_key
        card = prepare_card(dict(ULTRA_MILK))
        self.assertTrue(passes_filters(card, [], ["unicorn"], "any", []))      # change: unknown label is ignored, not a crash
        self.assertEqual(best_grade_key(card), 56.5)
        self.assertEqual(best_grade_key(prepare_card({"code": "x"})), -1)     # change: no grade -> goes last
        self.assertEqual(preference_fit({}, {"diet": "pescatarian", "off_tags": []})["status"], "unknown")
        self.assertEqual(preference_fit({}, {"diet": "none", "off_tags": ["en:milk"]})["text"], "? Can't verify allergens")

    # views.py: ?show=abc, sort by best grade, and the redirect after a click without JavaScript
    @patch("main.views.browse_products")
    def test_bad_show_value_and_sorting(self, fake_browse):
        fake_browse.return_value = [dict(ULTRA_MILK, code=str(i)) for i in range(8)] + [dict(OpenFoodFactsTests.GRADE_A)]
        response = self.client.get(reverse("main:show_main"), {"show": "abc"})
        self.assertEqual(len(response.context["products"]), 6)                 # change: rubbish value -> back to 6 cards
        response = self.client.get(reverse("main:show_main"), {"sort": "grade"})
        self.assertEqual(response.context["products"][0]["code"], "1")         # change: grade A jumps to the front
        self.assertNotIn("sort=", response.context["sort_url"])                # change: clicking again switches sorting off

    def test_redirects_go_back_only_to_our_own_site(self):
        self.client.force_login(self.user)
        heart = self.client.post(reverse("main:toggle_favorite", args=["1"]), {"next": "/?q=susu"})
        self.assertRedirects(heart, "/?q=susu", fetch_redirect_response=False)   # change: our own page -> allowed
        compare = self.client.post(reverse("main:add_to_compare", args=["1"]), {"next": "https://evil.example"})
        self.assertRedirects(compare, reverse("main:show_main"), fetch_redirect_response=False)   # change: other site -> blocked


# change: step 1, input safety. Nothing a user types or posts can break the API URL, the cache or the page
class InputSafetyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="safe", password="test-pass-123")

    # --- helpers in openfoodfacts.py ---
    def test_only_digit_barcodes_are_valid(self):
        self.assertTrue(off.is_valid_barcode("8998009010637"))
        for bad in ["", "12a", "../../etc", "1 2", "1" * 33, None]:
            self.assertFalse(off.is_valid_barcode(bad), bad)       # change: letters, slashes, spaces, too long -> refused

    def test_search_text_is_cleaned(self):
        self.assertEqual(off.clean_query("  <b>Susu</b>   UHT "), "Susu UHT")   # change: tags gone, spaces squeezed
        self.assertEqual(len(off.clean_query("a" * 300)), off.MAX_QUERY_LENGTH)

    def test_cache_keys_have_no_spaces(self):
        key = off.cache_key("search", "susu uht")
        self.assertNotIn(" ", key)                                  # change: fixes the CacheKeyWarning
        self.assertEqual(key, off.cache_key("search", "susu uht"))  # change: same text -> same key, so caching still works

    @patch("main.services.openfoodfacts.requests.get")
    def test_bad_barcode_never_reaches_the_api(self, fake_get):
        self.assertIsNone(off.get_product("../../etc"))
        fake_get.assert_not_called()

    # --- views ---
    def test_detail_page_404_for_bad_barcode(self):
        response = self.client.get("/product/abc/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "main/product_detail.html")   # change: our own page, not Django's error page
        self.assertContains(response, "find this product", status_code=404)
        self.assertContains(response, "Go to Discover", status_code=404)

    def test_detail_overlay_404_for_bad_barcode(self):
        response = self.client.get("/product/abc/", {"fragment": "1"})
        self.assertEqual(response.status_code, 404)
        self.assertIn("message", response.json())                  # change: Alyssa's overlay still gets JSON it can show

    def test_heart_refuses_bad_barcode(self):
        self.client.force_login(self.user)
        response = self.client.post("/favorite/abc/")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(FavoriteProduct.objects.exists())

    def test_heart_strips_html_from_the_name(self):
        self.client.force_login(self.user)
        self.client.post(reverse("main:toggle_favorite", args=["111"]), {"product_name": "<b>Ultra</b> Milk"})
        self.assertEqual(FavoriteProduct.objects.get().product_name, "Ultra Milk")

    def test_compare_cleans_name_and_grade(self):
        self.client.force_login(self.user)
        self.client.post(reverse("main:add_to_compare", args=["111"]), {"product_name": "<i>Milk</i>", "grade": "Z"})
        self.client.post(reverse("main:add_to_compare", args=["222"]), {"product_name": "Tea", "grade": "b"})
        info = self.client.session["compare_info"]
        self.assertEqual(info["111"], {"name": "Milk", "grade": "?"})   # change: unknown letter -> "?"
        self.assertEqual(info["222"]["grade"], "B")

    def test_compare_refuses_bad_barcode(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post("/tray/add/abc/").status_code, 404)
        self.assertEqual(self.client.session.get("compare", []), [])
        self.assertEqual(self.client.post("/tray/remove/abc/").status_code, 404)   # change: removing checks too

    @patch("main.views.search_products", return_value=[])
    def test_long_or_html_search_is_cleaned(self, fake_search):
        response = self.client.get(reverse("main:show_main"), {"q": "<b>susu</b> " + "a" * 300})
        self.assertEqual(len(response.context["q"]), off.MAX_QUERY_LENGTH)
        self.assertNotIn("<b>", response.context["q"])
        fake_search.assert_called_once_with(response.context["q"])


# change: step 2, custom security decorators (main/decorators.py)
AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class LoginRequiredJsonTests(TestCase):
    def test_logged_out_click_with_javascript_gets_401_json(self):
        response = self.client.post(reverse("main:toggle_favorite", args=["111"]), **AJAX)
        self.assertEqual(response.status_code, 401)                 # change: 401 = "log in first", not a redirect
        data = response.json()
        self.assertIn("message", data)
        self.assertTrue(data["login_url"].startswith(reverse("login") + "?next="))

    def test_htmx_request_also_gets_json(self):
        response = self.client.post(reverse("main:add_to_compare", args=["111"]), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 401)

    def test_normal_form_still_redirects_to_login(self):
        response = self.client.post(reverse("main:toggle_favorite", args=["111"]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)


class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()                                               # change: every test starts with fresh counters
        from django.test import Client
        self.client = Client(HTTP_HOST="localhost")                 # change: a real host name, so the limits are switched on
        self.user = get_user_model().objects.create_user(username="busy", password="test-pass-123")
        self.other = get_user_model().objects.create_user(username="calm", password="test-pass-123")

    def test_too_many_hearts_get_429_with_a_message(self):
        from main.decorators import FAVORITE_LIMIT
        self.client.force_login(self.user)
        url = reverse("main:toggle_favorite", args=["111"])
        for _ in range(FAVORITE_LIMIT):
            self.assertEqual(self.client.post(url, **AJAX).status_code, 200)
        response = self.client.post(url, **AJAX)
        self.assertEqual(response.status_code, 429)                 # change: 429 = "too many requests"
        self.assertIn("message", response.json())
        self.assertIn("Retry-After", response.headers)

    def test_each_user_has_their_own_limit(self):
        from main.decorators import FAVORITE_LIMIT
        url = reverse("main:toggle_favorite", args=["111"])
        self.client.force_login(self.user)
        for _ in range(FAVORITE_LIMIT + 1):
            self.client.post(url, **AJAX)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, **AJAX).status_code, 200)   # change: someone else isn't blocked

    @patch("main.views.search_products", return_value=[])
    def test_too_many_searches_show_a_friendly_page(self, fake_search):
        from main.decorators import SEARCH_LIMIT
        for i in range(SEARCH_LIMIT):
            self.client.get(reverse("main:show_main"), {"q": f"susu {i}"})
        response = self.client.get(reverse("main:show_main"), {"q": "susu"})
        self.assertEqual(response.status_code, 429)
        self.assertTemplateUsed(response, "main/too_many_requests.html")   # change: our own page, not an error page
        self.assertEqual(fake_search.call_count, SEARCH_LIMIT)            # change: the blocked request never reached the API

    def test_compare_has_a_limit_too(self):
        from main.decorators import COMPARE_LIMIT
        self.client.force_login(self.user)
        for _ in range(COMPARE_LIMIT):
            self.client.post(reverse("main:remove_from_compare", args=["111"]), **AJAX)
        response = self.client.post(reverse("main:add_to_compare", args=["111"]), **AJAX)
        self.assertEqual(response.status_code, 429)                 # change: add and remove share one counter

    def test_other_tests_are_not_counted(self):
        from main.decorators import FAVORITE_LIMIT
        from django.test import Client
        test_client = Client()                                      # change: the default "testserver" client
        test_client.force_login(self.user)
        url = reverse("main:toggle_favorite", args=["111"])
        for _ in range(FAVORITE_LIMIT + 1):
            response = test_client.post(url, **AJAX)
        self.assertEqual(response.status_code, 200)

    def test_counter_that_just_expired_starts_again(self):
        self.client.force_login(self.user)
        with patch("main.decorators.cache.incr", side_effect=ValueError):   # change: the key vanished between add and incr
            response = self.client.post(reverse("main:toggle_favorite", args=["111"]), **AJAX)
        self.assertEqual(response.status_code, 200)

    def test_logged_out_visitors_are_counted_by_ip(self):
        from main.decorators import client_id
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="10.0.0.5, 10.0.0.1")
        request.user = AnonymousUser()
        self.assertEqual(client_id(request), "ip:10.0.0.5")          # change: the first address is the visitor's own


# change: step 3a, what happens when Open Food Facts is down (main + backup both fail)
@patch("main.services.openfoodfacts.requests.get")
class ApiDownTests(TestCase):
    def setUp(self):
        cache.clear()

    def expire_fresh_copy(self, key):
        cache.delete(key)                                           # change: like the 1-hour cache running out

    def test_search_falls_back_to_the_last_good_copy(self, fake_get):
        fake_get.return_value = fake_response({"products": [ULTRA_MILK]})
        fresh = off.search_products("susu")
        self.assertFalse(off.is_stale(fresh))                       # change: fresh from the API
        self.expire_fresh_copy(off.cache_key("search", "susu"))
        fake_get.side_effect = API_DOWN                             # change: main API and backup both fail now
        saved = off.search_products("susu")
        self.assertEqual(saved, [ULTRA_MILK])                       # change: the saved copy, still a normal list for everyone
        self.assertTrue(off.is_stale(saved))                        # change: ...but marked as "saved earlier"

    def test_browse_falls_back_too(self, fake_get):
        fake_get.return_value = fake_response({"products": [ULTRA_MILK]})
        off.browse_products()
        self.expire_fresh_copy("off:browse")
        fake_get.side_effect = API_DOWN
        saved = off.browse_products()
        self.assertEqual(saved, [ULTRA_MILK])
        self.assertTrue(off.is_stale(saved))

    def test_product_falls_back_to_its_last_good_copy(self, fake_get):
        fake_get.return_value = fake_response({"product": ULTRA_MILK})
        off.get_product(ULTRA_MILK["code"])
        self.expire_fresh_copy(f"off:product:{ULTRA_MILK['code']}")
        fake_get.side_effect = API_DOWN
        self.assertEqual(off.get_product(ULTRA_MILK["code"]), ULTRA_MILK)   # change: same signature, Alyssa's page keeps working

    def test_nothing_saved_yet_still_means_none(self, fake_get):
        fake_get.side_effect = API_DOWN
        self.assertIsNone(off.search_products("susu"))

    def test_after_a_failure_the_api_is_left_alone_for_a_while(self, fake_get):
        fake_get.side_effect = API_DOWN
        off.search_products("susu")
        calls = fake_get.call_count                                 # change: main + backup were tried once
        off.search_products("teh")
        off.get_product(ULTRA_MILK["code"])
        self.assertEqual(fake_get.call_count, calls)                # change: no new calls while it's marked as down
        cache.delete(off.DOWN_KEY)                                  # change: when the 90 seconds are over...
        off.search_products("teh")
        self.assertGreater(fake_get.call_count, calls)              # ...it tries again

    def test_broken_json_counts_as_a_failure(self, fake_get):
        broken = MagicMock()
        broken.json.side_effect = ValueError("not JSON")            # change: e.g. an HTML error page instead of JSON
        fake_get.side_effect = [broken, fake_response({"hits": [ULTRA_MILK]})]
        self.assertEqual(off.search_products("susu"), [ULTRA_MILK])   # change: treated as a failure -> backup used

    def test_json_that_is_not_an_object_counts_as_a_failure(self, fake_get):
        fake_get.side_effect = [fake_response(["weird"]), fake_response(["weird"])]
        self.assertIsNone(off.search_products("susu"))

    def test_product_answer_that_is_not_an_object_counts_as_a_failure(self, fake_get):
        fake_get.return_value = fake_response(["weird"])
        self.assertIsNone(off.get_product(ULTRA_MILK["code"]))
        self.assertTrue(cache.get(off.DOWN_KEY))                    # change: marked as down

    def test_missing_product_is_not_a_failure(self, fake_get):
        fake_get.return_value = fake_response({"status": 0})       # change: the API answered, the product just doesn't exist
        self.assertIsNone(off.get_product("0000000000000"))
        self.assertIsNone(cache.get(off.DOWN_KEY))                  # change: so the API isn't marked as down

    @patch("main.views.search_products", return_value=off.StaleList([dict(ULTRA_MILK)]))
    def test_page_tells_the_user_these_are_saved_results(self, fake_search, fake_get):
        response = self.client.get(reverse("main:show_main"), {"q": "susu"})
        self.assertContains(response, "Ultra Milk Low Fat")
        self.assertContains(response, 'data-message="Open Food Facts isn&#x27;t responding')   # change: sent to the shared toast
        self.assertTrue(response.context["stale"])

    @patch("main.views.browse_products", return_value=[dict(ULTRA_MILK)])
    def test_fresh_results_have_no_note(self, fake_browse, fake_get):
        response = self.client.get(reverse("main:show_main"))
        self.assertNotContains(response, "saved earlier")
        self.assertFalse(response.context["stale"])

