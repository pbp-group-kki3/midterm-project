from django.test import TestCase

# Create your tests here.
from django.test import SimpleTestCase
from django.template.loader import render_to_string

from comparison.services import (
    NUTRIENT_RULES,
    build_nutrition_rows,
    build_ranked_cells,
    build_score_rows,
)


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
from unittest.mock import patch
from django.contrib.auth.models import User
from django.urls import reverse
from comparison.models import SavedComparison


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
