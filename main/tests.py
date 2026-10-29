from django.test import TestCase
from unittest.mock import patch

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

