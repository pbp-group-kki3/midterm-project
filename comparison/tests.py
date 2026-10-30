from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import Client, SimpleTestCase, TestCase
from django.template.loader import render_to_string
from django.urls import reverse

from comparison.forms import SavedComparisonEditForm, SavedComparisonForm
from comparison.models import SavedComparison
from comparison.services import (
    NUTRIENT_RULES,
    build_comparison_sections,
    build_label_rows,
    build_nutrition_rows,
    build_ranked_cells,
    build_score_rows,
    format_tags,
    get_numeric_value,
    load_comparison_products,
    normalize_grade,
    normalize_nova,
)
from main.models import FavoriteProduct

# =============================================================================
# 1. HIGHLIGHTING AND COMPARISON RULES
# Covers: Scores and nutrition: best values, ties, missing/invalid data, zero, and help text.
# =============================================================================
class ComparisonHighlightTests(SimpleTestCase):
    # Help text must describe comparing available values instead of rejecting incomplete rows.
    def test_header_explains_comparing_available_values(self):
        html = render_to_string('comparison/compare.html', {
            'products': [],
            'show_compare_panel': False,
        })
        self.assertIn('at least two products have comparable data', html)
        self.assertIn('all comparable values are equal', html)
        self.assertNotIn('Equal or incomplete rows are not highlighted.', html)

    def test_ranked_cells_compare_only_available_values(self):
        cases = [
            ([3, 1, 2], [False, True, False]),
            ([3, 1, None], [False, True, False]),
            ([None, 3, 1], [False, False, True]),
            ([3, None, None], [False, False, False]),
            ([3, None], [False, False]),
            ([None, None, None], [False, False, False]),
            ([1, 1, None], [False, False, False]),
            ([1, 1, 3], [True, True, False]),
            ([0, 3, None], [True, False, False]),
            ([3, 1], [False, True]),
        ]

        for ranks, expected in cases:
            with self.subTest(ranks=ranks):
                displays = [
                    "Not available" if rank is None else str(rank)
                    for rank in ranks
                ]

                cells = build_ranked_cells(displays, ranks)

                self.assertEqual(
                    [cell["is_better"] for cell in cells],
                    expected,
                )
                self.assertEqual(
                    [cell["display"] for cell in cells],
                    displays,
                )

    def test_nutrition_rows_respect_availability_and_direction(self):
        cases = [
            ([8, 2, 5], [False, True, False], [True, False, False]),
            ([8, 2, None], [False, True, False], [True, False, False]),
            ([None, 8, 2], [False, False, True], [False, True, False]),
            ([8, None, None], [False] * 3, [False] * 3),
            ([8, None], [False] * 2, [False] * 2),
            ([None, None, None], [False] * 3, [False] * 3),
            ([2, 2, None], [False] * 3, [False] * 3),
            ([2, 2, 8], [True, True, False], [False, False, True]),
            ([0, 2, None], [True, False, False], [False, True, False]),
            ([8, 2], [False, True], [True, False]),
        ]

        for label, field, unit, direction in NUTRIENT_RULES:
            for values, lower_expected, higher_expected in cases:
                with self.subTest(field=field, values=values):
                    products = [
                        {"nutriments": {field: value}}
                        for value in values
                    ]

                    rows = build_nutrition_rows(products)
                    row = next(
                        row for row in rows
                        if row["label"] == label
                    )

                    expected = (
                        lower_expected
                        if direction == "lower"
                        else higher_expected
                    )

                    self.assertEqual(
                        [cell["is_better"] for cell in row["cells"]],
                        expected,
                    )

                    for value, cell in zip(values, row["cells"]):
                        if value is None:
                            self.assertEqual(
                                cell["display"],
                                "Not available",
                            )
                            self.assertFalse(cell["is_better"])

    def test_missing_nutrition_does_not_disable_other_rows(self):
        products = [
            {
                "nutriments": {
                    "fat_100g": 8,
                    "proteins_100g": 2,
                },
            },
            {
                "nutriments": {
                    "fat_100g": 2,
                    "proteins_100g": 8,
                },
            },
            {
                "nutriments": {
                    "proteins_100g": 5,
                },
            },
        ]

        rows = {
            row["label"]: row
            for row in build_nutrition_rows(products)
        }

        self.assertEqual(
            [cell["is_better"] for cell in rows["Fat"]["cells"]],
            [False, True, False],
        )
        self.assertEqual(
            [cell["is_better"] for cell in rows["Protein"]["cells"]],
            [False, True, False],
        )

    def test_invalid_values_are_missing_but_zero_is_available(self):
        for missing_value in [
            None,
            "",
            "unknown",
            True,
            -1,
            float("nan"),
            float("inf"),
        ]:
            with self.subTest(missing_value=missing_value):
                products = [
                    {"nutriments": {"fat_100g": 0}},
                    {"nutriments": {"fat_100g": 2}},
                    {"nutriments": {"fat_100g": missing_value}},
                ]

                row = next(
                    row for row in build_nutrition_rows(products)
                    if row["label"] == "Fat"
                )

                self.assertEqual(row["cells"][0]["display"], "0 g")
                self.assertEqual(
                    [cell["is_better"] for cell in row["cells"]],
                    [True, False, False],
                )
                self.assertEqual(
                    row["cells"][2]["display"],
                    "Not available",
                )

    def test_score_rows_compare_two_available_products(self):
        products = [
            {
                "compare_grade": "D",
                "compare_score": 25,
                "nutriscore_grade": "e",
                "ecoscore_grade": "d",
                "nova_group": 2,
            },
            {
                "compare_grade": "C",
                "compare_score": 50,
                "nutriscore_grade": "d",
                "ecoscore_grade": "c",
                "nova_group": 3,
            },
            {},
        ]

        rows = {
            row["label"]: row
            for row in build_score_rows(products)
        }

        expected_by_label = {
            "SpoonFeed grade": [False, True, False],
            "Nutri-Score": [False, True, False],
            "Green-Score": [False, True, False],
            "Processing (NOVA)": [True, False, False],
        }

        for label, expected in expected_by_label.items():
            with self.subTest(label=label):
                self.assertEqual(
                    [cell["is_better"] for cell in rows[label]["cells"]],
                    expected,
                )
                self.assertEqual(
                    rows[label]["cells"][2]["display"],
                    "Not available",
                )

# change: a comparison opened from Saved goes back to Saved, a normal one back to Discover
# =============================================================================
# 2. BACK NAVIGATION
# Covers: Normal Comparison returns to Discover; saved comparisons return to Profile Saved.
# =============================================================================
class CompareBackLinkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='comparer', password='password123')
        self.client.force_login(self.user)

    @patch('comparison.views.load_comparison_products', return_value=([], []))
    def test_normal_compare_goes_back_to_discover(self, fake_load):
        response = self.client.get(reverse('comparison:compare_products'))
        self.assertContains(response, 'Back to Discover')
        self.assertNotContains(response, 'Back to Saved')

    def test_saved_compare_goes_back_to_saved(self):
        saved = SavedComparison.objects.create(user=self.user, name='Saved lineup', barcodes=['111', '222'])
        products = [{'compare_barcode': code, 'product_name': 'Example', 'nutriments': {}} for code in saved.barcodes]
        with patch('comparison.views.load_comparison_products', return_value=(products, [])):
            response = self.client.get(reverse('profile_saved_comparison', args=[saved.pk]))
        self.assertContains(response, 'Back to Saved')
        self.assertNotContains(response, 'Back to Discover')

# =============================================================================
# 3. SAVED COMPARISON DETAILS, EDITING AND REMOVAL
# Covers: Metadata, validation, ownership, authentication, CSRF, feedback, and tray preservation.
# =============================================================================
class SavedComparisonTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("snapshot-owner")
        self.other = User.objects.create_user("snapshot-other")
        self.client.force_login(self.owner)

        self.saved = SavedComparison.objects.create(user=self.owner, name="Breakfast choices", notes="Before shopping", barcodes=["111", "222"])
        self.detail_url = reverse("profile_saved_comparison", args=[self.saved.pk])
        self.edit_url = reverse("comparison:edit_saved_comparison", args=[self.saved.pk])
        self.remove_url = reverse("comparison:remove_saved_comparison", args=[self.saved.pk])

        self.tray = {
            "compare": ["999", "888"], 
            "compare_info": {"999": {"name": "Active product"}}, 
            "compare_has_removed": True, 
            "comparison_save_errors": {"data": {"name": "Unfinished draft"}},
            }
        session = self.client.session
        session.update(self.tray)
        session.save()

    def assert_tray_preserved(self):
        session = self.client.session
        for key, value in self.tray.items():
            self.assertEqual(session[key], value, key)

    def products(self):
        return [{"compare_barcode": code, "product_name": f"Product {code}", "nutriments": {}} for code in self.saved.barcodes]

    def test_saved_view_uses_record_metadata_and_lineup(self):
        with patch("comparison.views.load_comparison_products", return_value=(self.products(), [])) as loader:
            response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        loader.assert_called_once_with(["111", "222"])
        self.assertEqual(response.context["saved_comparison"].pk, self.saved.pk)
        self.assertContains(response, self.saved.name)
        self.assertContains(response, self.saved.notes)
        self.assertContains(response, "Back to Saved")
        self.assertContains(response, "js-product-detail")
        self.assertNotContains(response, 'id="compare-save-location"')
        self.assertNotContains(response, 'id="compare-save-dialog"')
        self.assertNotContains(response, "compare-remove-trigger")
        self.assert_tray_preserved()

    def test_empty_notes_have_a_hidden_description(self):
        self.saved.notes = ""
        self.saved.save(update_fields=["notes"])

        with patch("comparison.views.load_comparison_products", return_value=([], [])):
            response = self.client.get(self.detail_url)

        self.assertContains(response, '<p id="compare-saved-notes" class="page-subtitle compare-saved-notes" hidden></p>', html=True)

    def test_edit_form_does_not_require_selection(self):
        form = SavedComparisonEditForm({"edit-name": "Updated", "edit-notes": ""}, instance=self.saved, prefix="edit")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("selection", form.fields)
        self.assertIn("selection", SavedComparisonForm().fields)

    def test_edit_updates_metadata_only(self):
        response = self.client.post(self.edit_url, {"edit-name": "Updated choices", "edit-notes": "New notes", "barcodes": ["999"], "user": self.other.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["comparison"]["id"], self.saved.pk)
        self.saved.refresh_from_db()
        self.assertEqual(self.saved.name, "Updated choices")
        self.assertEqual(self.saved.notes, "New notes")
        self.assertEqual(self.saved.barcodes, ["111", "222"])
        self.assertEqual(self.saved.user_id, self.owner.pk)
        self.assert_tray_preserved()

    def test_invalid_edits_preserve_the_record(self):
        cases = [
            ({"edit-name": " ", "edit-notes": ""}, "name"), 
            ({"edit-name": "x" * 151, "edit-notes": ""}, "name"), 
            ({"edit-name": "Valid", "edit-notes": "x" * 2001}, "notes"),
            ]
        for data, field in cases:
            with self.subTest(field=field, data_length=len(str(data))):
                response = self.client.post(self.edit_url, data)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json()["errors"])
                self.saved.refresh_from_db()
                self.assertEqual(self.saved.name, "Breakfast choices")
                self.assertEqual(self.saved.notes, "Before shopping")
                self.assertEqual(self.saved.barcodes, ["111", "222"])
                self.assert_tray_preserved()

    def test_other_users_cannot_view_edit_or_remove(self):
        self.client.force_login(self.other)

        self.assertEqual(self.client.get(self.detail_url).status_code, 404)
        self.assertEqual(self.client.post(self.edit_url, {"edit-name": "Not allowed", "edit-notes": ""}).status_code, 404)
        self.assertEqual(self.client.post(self.remove_url).status_code, 404)

        self.saved.refresh_from_db()
        self.assertEqual(self.saved.name, "Breakfast choices")

    def test_authentication_and_post_are_required(self):
        anonymous = Client()
        self.assertEqual(anonymous.get(self.detail_url).status_code, 302)
        self.assertEqual(anonymous.post(self.edit_url).status_code, 401)
        self.assertEqual(anonymous.post(self.remove_url).status_code, 401)
        self.assertEqual(self.client.get(self.edit_url).status_code, 405)
        self.assertEqual(self.client.get(self.remove_url).status_code, 405)
        self.assertTrue(SavedComparison.objects.filter(pk=self.saved.pk).exists())

    def test_remove_deletes_only_the_record_and_shows_feedback_once(self):
        favorite = FavoriteProduct.objects.create(user=self.owner, barcode="111")
        remaining = SavedComparison.objects.create(user=self.owner, name="Another comparison", barcodes=["333", "444"])

        response = self.client.post(self.remove_url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SavedComparison.objects.filter(pk=self.saved.pk).exists())
        self.assertTrue(SavedComparison.objects.filter(pk=remaining.pk).exists())
        self.assertTrue(FavoriteProduct.objects.filter(pk=favorite.pk).exists())
        self.assert_tray_preserved()

        destination = response.json()["redirect_url"]
        self.assertEqual(destination, reverse("profile_saved") + "?category=comparison")

        page = self.client.get(destination)
        self.assertNotContains(page, "Breakfast choices")
        self.assertContains(page, "Saved comparison removed.", count=1)

        next_page = self.client.get(destination)
        self.assertNotContains(next_page, "Saved comparison removed.")

    def test_mutations_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)

        with patch("comparison.views.load_comparison_products", return_value=([], [])):
            client.get(self.detail_url)

        token = client.cookies["csrftoken"].value
        data = {"edit-name": "CSRF checked", "edit-notes": ""}

        self.assertEqual(client.post(self.edit_url, data).status_code, 403)
        self.assertEqual(client.post(self.remove_url).status_code, 403)

        response = client.post(self.edit_url, data, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

        response = client.post(self.remove_url, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

# Prepare product fixtures without making real API requests.
def comparison_product(barcode):
    return {
        "code": barcode, 
        "compare_barcode": barcode, 
        "product_name": f"Product {barcode}", 
        "nutriscore_grade": "c", 
        "ecoscore_grade": "c", 
        "nova_group": 2, 
        "compare_grade": "C", 
        "compare_score": 50, 
        "compare_nutri": "c", 
        "compare_green": "c", 
        "compare_nova": 2, 
        "nutriments": {},
        }


# =============================================================================
# 4. PRODUCT DATA AND COMPARISON SERVICES
# Covers: Normalization, labels, API loading, unavailable products, sections, and number formatting.
# =============================================================================
class ComparisonServiceTests(SimpleTestCase):
    # Invalid or missing values must not become valid comparison ranks.
    def test_grade_nova_and_numeric_normalization(self):
        grade_cases = [(" A ", "a"), ("e", "e"), ("unknown", None), (None, None), (2, None)]
        for value, expected in grade_cases:
            with self.subTest(kind="grade", value=value):
                self.assertEqual(normalize_grade(value), expected)

        nova_cases = [(1, 1), ("2", 2), (4.0, 4), (0, None), (2.5, None), (True, None)]
        for value, expected in nova_cases:
            with self.subTest(kind="nova", value=value):
                self.assertEqual(normalize_nova(value), expected)

        number_cases = [
            (0, 0), 
            ("2.5", 2.5), 
            (None, None), 
            ("unknown", None), 
            (False, None), 
            (-1, None), 
            (float("nan"), None), 
            (float("inf"), None),
        ]
        for value, expected in number_cases:
            with self.subTest(kind="number", value=value):
                self.assertEqual(get_numeric_value(value), expected)

    def test_labels_are_readable_unique_and_never_ranked(self):
        tags = ["en:palm-oil-free", "en:palm-oil-free", "en:halal", None, ""]
        self.assertEqual(format_tags(tags), "palm oil free, halal")
        self.assertEqual(format_tags("en:halal"), "Not available")
        self.assertEqual(format_tags([]), "Not available")

        rows = build_label_rows([{"labels_tags": tags, "allergens_tags": ["en:milk"]}, {}])

        self.assertEqual(rows[0]["cells"][0]["display"], "palm oil free, halal")
        self.assertEqual(rows[1]["cells"][0]["display"], "milk")
        self.assertEqual(rows[1]["cells"][1]["display"], "Not available")
        self.assertTrue(all(not cell["is_better"] for row in rows for cell in row["cells"]))

    def test_product_loading_keeps_available_order_and_source_data(self):
        first = {"code": "111", "nutriscore_grade": " B ", "ecoscore_grade": "d", "nova_group": "2"}
        third = {"code": "333", "nutriscore_grade": "a", "ecoscore_grade": "b", "nova_group": 1}
        original = first.copy()

        with patch("comparison.services.get_product", side_effect=[first, None, third]) as fetch:
            with patch("comparison.services.spoonfeed_grade", return_value={"grade": "B", "score": 70}):
                products, unavailable = load_comparison_products(["111", "222", "333"])

        self.assertEqual([call.args[0] for call in fetch.call_args_list], ["111", "222", "333"])
        self.assertEqual([product["compare_barcode"] for product in products], ["111", "333"])
        self.assertEqual(unavailable, ["222"])
        self.assertEqual(products[0]["compare_nutri"], "b")
        self.assertEqual(products[0]["compare_nova"], 2)
        self.assertEqual(products[0]["compare_score"], 70)
        self.assertEqual(first, original)
        self.assertIsNot(products[0], first)

    def test_all_unavailable_products_return_an_empty_product_list(self):
        with patch("comparison.services.get_product", return_value=None):
            with patch("comparison.services.spoonfeed_grade") as grade:
                products, unavailable = load_comparison_products(["111", "222"])

        self.assertEqual(products, [])
        self.assertEqual(unavailable, ["111", "222"])
        grade.assert_not_called()

    def test_sections_keep_scores_nutrition_labels_and_allergens(self):
        nutrition = build_nutrition_rows([comparison_product("111")])
        sections = build_comparison_sections([comparison_product("111")], nutrition)

        self.assertEqual([section["title"] for section in sections], ["Scores", "Nutrition per 100 g/ml", "Labels and allergens"])
        self.assertIs(sections[1]["rows"], nutrition)
        self.assertEqual([row["label"] for row in sections[2]["rows"]], ["Labels", "Allergens"])

    def test_nutrition_formats_decimal_zero_and_missing_values(self):
        products = [{"nutriments": {"fat_100g": "2.50"}}, {"nutriments": {"fat_100g": 0}}, {}]
        row = next(row for row in build_nutrition_rows(products) if row["label"] == "Fat")

        self.assertEqual([cell["display"] for cell in row["cells"]], ["2.5 g", "0 g", "Not available"])
        self.assertEqual([cell["is_better"] for cell in row["cells"]], [False, True, False])


# =============================================================================
# 5. ACTIVE COMPARISON PAGE, SAVE AND PRODUCT REMOVAL
# Covers: Page states, session selection, save validation, duplicates, API failures, CSRF, and removal.
# =============================================================================
class ComparisonEndpointTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("comparison-endpoint-owner")
        self.other = User.objects.create_user("comparison-endpoint-other")
        self.client.force_login(self.owner)

        self.codes = ["111", "222"]
        self.info = {"111": {"name": "First"}, "222": {"name": "Second"}}
        self.compare_url = reverse("comparison:compare_products")
        self.save_url = reverse("comparison:save_comparison")
        self.data = {"name": "Breakfast choices", "notes": "", "selection": "111,222"}

        self.set_lineup(self.codes, compare_info=self.info, compare_has_removed=False, comparison_save_errors={"data": {"name": "Old draft"}})

    # Change only the test client's session, never real user records.
    def set_lineup(self, value, client=None, **extra):
        client = client or self.client
        session = client.session
        session["compare"] = value
        session.update(extra)
        session.save()

    def test_page_states_for_zero_one_two_and_three_products(self):
        for count in range(4):
            codes = ["111", "222", "333"][:count]
            self.set_lineup(codes)
            products = [comparison_product(code) for code in codes]

            with self.subTest(count=count):
                with patch("comparison.views.load_comparison_products", return_value=(products, [])) as loader:
                    response = self.client.get(self.compare_url)

                self.assertEqual(response.status_code, 200)
                loader.assert_called_once_with(codes)
                self.assertEqual(response.context["can_save"], count >= 2)
                self.assertEqual(response.context["show_compare_panel"], count > 0)
                self.assertEqual(self.client.session["compare"], codes)

                self.assertContains(response, "Back to Discover")
                self.assertNotContains(response, "Back to Saved")
                self.assertContains(response, 'id="compare-save-dialog"')
                self.assertNotContains(response, 'id="compare-edit-dialog"')

    def test_page_deduplicates_and_limits_display_without_replacing_tray(self):
        codes = ["111", "111", "222", "333", "444"]
        self.set_lineup(codes)
        products = [comparison_product(code) for code in ["111", "222", "333"]]

        with patch("comparison.views.load_comparison_products", return_value=(products, [])) as loader:
            response = self.client.get(self.compare_url)

        self.assertEqual(response.status_code, 200)
        loader.assert_called_once_with(["111", "222", "333"])
        self.assertEqual(self.client.session["compare"], codes)

    def test_unavailable_product_disables_creation_and_warns_once(self):
        with patch("comparison.views.load_comparison_products", return_value=([comparison_product("111")], ["222"])):
            response = self.client.get(self.compare_url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_save"])
        self.assertContains(response, "Some selected products could not be loaded.", count=1)
        self.assertEqual(self.client.session["compare"], self.codes)

    def test_saved_status_is_scoped_to_the_current_user(self):
        SavedComparison.objects.create(user=self.other, name="Private", barcodes=self.codes)
        products = [comparison_product(code) for code in self.codes]

        with patch("comparison.views.load_comparison_products", return_value=(products, [])):
            response = self.client.get(self.compare_url)
            self.assertFalse(response.context["is_saved"])

            SavedComparison.objects.create(user=self.owner, name="Mine", barcodes=self.codes)
            response = self.client.get(self.compare_url)
            self.assertTrue(response.context["is_saved"])

    def test_compare_page_rejects_post_without_loading_products(self):
        with patch("comparison.views.load_comparison_products") as loader:
            response = self.client.post(self.compare_url)

        self.assertEqual(response.status_code, 405)
        loader.assert_not_called()
        self.assertEqual(self.client.session["compare"], self.codes)

    def test_add_slot_appears_after_removal_but_not_when_full(self):
        cases = [(["111", "222"], True), (["111", "222", "333"], False)]
        for codes, expected in cases:
            self.set_lineup(codes, compare_has_removed=True)
            products = [comparison_product(code) for code in codes]

            with self.subTest(codes=codes):
                with patch("comparison.views.load_comparison_products", return_value=(products, [])):
                    response = self.client.get(self.compare_url)
                self.assertEqual(response.context["show_add_product"], expected)

    # Creation must use the logged-in owner and retain the active tray.
    def test_save_two_and_three_products_with_server_owned_metadata(self):
        for codes in [["111", "222"], ["111", "222", "333"]]:
            self.set_lineup(codes)
            data = {**self.data, "selection": ",".join(codes), "user": self.other.pk}

            with self.subTest(codes=codes):
                with patch("comparison.views.get_product", side_effect=comparison_product) as fetch:
                    response = self.client.post(self.save_url, data)

                self.assertEqual(response.status_code, 201)
                self.assertTrue(response.json()["ok"])
                self.assertFalse(response.json()["already_saved"])

                record = SavedComparison.objects.get(user=self.owner, barcodes=codes)
                self.assertEqual(record.name, self.data["name"])
                self.assertEqual(record.notes, "")
                self.assertEqual(fetch.call_count, len(codes))
                self.assertEqual(self.client.session["compare"], codes)
                self.assertEqual(self.client.session["compare_info"], self.info)
                self.assertNotIn("comparison_save_errors", self.client.session)

        self.assertEqual(SavedComparison.objects.filter(user=self.owner).count(), 2)

    def test_save_deduplicates_barcodes_without_rewriting_tray(self):
        codes = ["111", "222", "111"]
        self.set_lineup(codes)

        with patch("comparison.views.get_product", side_effect=comparison_product) as fetch:
            response = self.client.post(self.save_url, self.data)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(SavedComparison.objects.get(user=self.owner).barcodes, ["111", "222"])
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(self.client.session["compare"], codes)

    def test_save_retry_does_not_duplicate_or_reuse_another_users_record(self):
        other_record = SavedComparison.objects.create(user=self.other, name="Private", barcodes=self.codes)
        with patch("comparison.views.get_product", side_effect=comparison_product):
            first = self.client.post(self.save_url, self.data)

        self.assertEqual(first.status_code, 201)

        with patch("comparison.views.get_product") as fetch:
            retry = self.client.post(self.save_url, {**self.data, "name": "Changed on retry"})

        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json()["already_saved"])
        fetch.assert_not_called()
        self.assertEqual(SavedComparison.objects.filter(user=self.owner).count(), 1)
        self.assertEqual(SavedComparison.objects.get(user=self.owner).name, self.data["name"])
        self.assertTrue(SavedComparison.objects.filter(pk=other_record.pk).exists())

    def test_invalid_creation_fields_do_not_save_or_call_api(self):
        cases = [
            ({**self.data, "name": " "}, "name"), 
            ({**self.data, "name": "x" * 151}, "name"), 
            ({**self.data, "notes": "x" * 2001}, "notes"), 
            ({"name": "Valid", "notes": ""}, "selection"),
        ]

        for data, field in cases:
            with self.subTest(field=field):
                with patch("comparison.views.get_product") as fetch:
                    response = self.client.post(self.save_url, data)

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json()["errors"])
                fetch.assert_not_called()
                self.assertEqual(SavedComparison.objects.count(), 0)
                self.assertEqual(self.client.session["compare"], self.codes)
                self.assertIn("comparison_save_errors", self.client.session)

    def test_changed_or_reordered_selection_is_rejected(self):
        for selection in ["111,333", "222,111"]:
            with self.subTest(selection=selection):
                with patch("comparison.views.get_product") as fetch:
                    response = self.client.post(self.save_url, {**self.data, "selection": selection})

                self.assertEqual(response.status_code, 400)
                self.assertIn("__all__", response.json()["errors"])
                fetch.assert_not_called()
                self.assertFalse(SavedComparison.objects.exists())

    def test_invalid_session_selections_are_rejected_by_save(self):
        values = [
            None, 
            "111,222", 
            {"first": "111"}, 
            [], 
            ["111"], 
            ["111", "222", "333", "444"], 
            ["111", "invalid"], 
            ["111", 222], 
            ["111", "١٢٣"], 
            ["111", ""], 
            ["111", "111"], 
            [["111"], "222"],
        ]

        for value in values:
            self.set_lineup(value)

            with self.subTest(value=value):
                with patch("comparison.views.get_product") as fetch:
                    response = self.client.post(self.save_url, self.data)

                self.assertEqual(response.status_code, 400)
                self.assertIn("__all__", response.json()["errors"])
                fetch.assert_not_called()
                self.assertFalse(SavedComparison.objects.exists())

    def test_unavailable_product_does_not_create_a_partial_record(self):
        for missing in [None, {}, [], "offline"]:
            with self.subTest(missing=missing):
                with patch("comparison.views.get_product", side_effect=[comparison_product("111"), missing],):
                    response = self.client.post(self.save_url, self.data)

                self.assertEqual(response.status_code, 400)
                self.assertIn("__all__", response.json()["errors"])
                self.assertFalse(SavedComparison.objects.exists())
                self.assertEqual(self.client.session["compare"], self.codes)

    def test_creation_requires_authentication_post_and_csrf(self):
        with patch("comparison.views.get_product") as fetch:
            self.assertEqual(Client().post(self.save_url, self.data).status_code, 401)
            self.assertEqual(self.client.get(self.save_url).status_code, 405)
            fetch.assert_not_called()

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.set_lineup(self.codes, client=client)

        with patch("comparison.views.load_comparison_products", return_value=([comparison_product(code) for code in self.codes], []),):
            client.get(self.compare_url)

        token = client.cookies["csrftoken"].value

        with patch("comparison.views.get_product", side_effect=comparison_product) as fetch:
            self.assertEqual(client.post(self.save_url, self.data).status_code, 403)
            fetch.assert_not_called()
            response = client.post(self.save_url, self.data, HTTP_X_CSRFTOKEN=token)

        self.assertEqual(response.status_code, 201)

    # Removing an active product must not delete an existing saved comparison.
    def test_remove_updates_only_active_tray_and_product_metadata(self):
        saved = SavedComparison.objects.create(user=self.owner, name="Keep saved", barcodes=self.codes)
        response = self.client.post(reverse("comparison:remove_product", args=["111"]))

        self.assertRedirects(response, self.compare_url, fetch_redirect_response=False)
        self.assertEqual(self.client.session["compare"], ["222"])
        self.assertEqual(self.client.session["compare_info"], {"222": self.info["222"]})
        self.assertTrue(self.client.session["compare_has_removed"])

        saved.refresh_from_db()
        self.assertEqual(saved.barcodes, self.codes)
        self.assertEqual([(message.level_tag, str(message)) for message in get_messages(response.wsgi_request)], [("success", "Product removed from comparison.")])

    def test_remove_unknown_barcode_does_not_change_the_tray(self):
        response = self.client.post(reverse("comparison:remove_product", args=["999"]))

        self.assertRedirects(response, self.compare_url, fetch_redirect_response=False)
        self.assertEqual(self.client.session["compare"], self.codes)
        self.assertEqual(self.client.session["compare_info"], self.info)
        self.assertFalse(self.client.session["compare_has_removed"])
        self.assertEqual([(message.level_tag, str(message)) for message in get_messages(response.wsgi_request)], [("warning", "This product is no longer in your comparison.")])

    def test_removing_twice_is_safe(self):
        url = reverse("comparison:remove_product", args=["111"])
        self.client.post(url)
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session["compare"], ["222"])
        self.assertEqual(self.client.session["compare_info"], {"222": self.info["222"]})
        self.assertEqual(list(get_messages(response.wsgi_request))[-1].level_tag, "warning")

    def test_remove_last_product_keeps_an_empty_tray(self):
        self.set_lineup(["111"], compare_info={"111": self.info["111"]})
        response = self.client.post(reverse("comparison:remove_product", args=["111"]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session["compare"], [])
        self.assertEqual(self.client.session["compare_info"], {})

    def test_remove_requires_post_and_csrf(self):
        url = reverse("comparison:remove_product", args=["111"])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.session["compare"], self.codes)

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.set_lineup(self.codes, client=client, compare_info=self.info)

        with patch("comparison.views.load_comparison_products", return_value=([comparison_product(code) for code in self.codes], []),):
            client.get(self.compare_url)

        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(url).status_code, 403)
        self.assertEqual(client.session["compare"], self.codes)

        response = client.post(url, HTTP_X_CSRFTOKEN=token)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session["compare"], ["222"])