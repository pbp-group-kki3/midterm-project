from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient

from comparison.models import SavedComparison


class ComparisonApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.owner = get_user_model().objects.create_user(username="owner")
        self.other = get_user_model().objects.create_user(username="other")
        self.codes = ["001", "002"]
        self.payload = {"name": "Breakfast", "notes": "Compare sugar", "barcodes": self.codes}
        self.preview = reverse("comparison_api:preview")
        self.saved = reverse("comparison_api:saved_list")
        lookup = patch("comparison.services.get_product", side_effect={
            "001": {"product_name": "Milk", "nutriments": {"sugars_100g": 3}},
            "002": {"product_name": "Oat drink", "nutriments": {"sugars_100g": 5}},
        }.get)
        self.lookup = lookup.start()
        self.addCleanup(lookup.stop)

    def test_guest_preview_preserves_order_and_partial_results(self):
        response = self.client.get(self.preview, {"barcode": [*self.codes, "003"]})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([p["barcode"] for p in data["products"]], self.codes)
        self.assertEqual(data["unavailable_barcodes"], ["003"])
        rows = data["sections"][1]["rows"]
        sugar = next(row for row in rows if row["label"] == "Sugars")
        self.assertEqual([cell["is_better"] for cell in sugar["cells"]], [True, False])

    def test_invalid_selection_is_rejected_before_lookup(self):
        self.client.force_login(self.owner)
        for codes in ([], ["001"], ["001"] * 2, ["1", "2", "3", "4"],
                      ["001", "１２"], ["1", "2" * 33], ["001", 2], ["001", None]):
            with self.subTest(codes=codes):
                response = self.client.post(self.saved, {**self.payload, "barcodes": codes}, format="json")
                self.assertEqual(response.status_code, 400)
        self.lookup.assert_not_called()

    def test_unavailable_products_cannot_be_saved(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.saved, {**self.payload, "barcodes": ["001", "003"]}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["unavailable_barcodes"], ["003"])
        self.assertFalse(SavedComparison.objects.exists())

    def test_native_session_can_manage_and_reopen_its_saved_lineup(self):
        self.client.force_login(self.owner)
        result = self.client.post(self.saved, self.payload, format="json")
        self.assertEqual(result.status_code, 201)
        record = result.json()
        detail = reverse("comparison_api:saved_detail", args=[record["id"]])
        retry = self.client.post(self.saved, self.payload, format="json")
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json(), record)
        self.assertEqual(self.client.get(self.saved).json(), [record])
        self.assertEqual(self.client.get(detail).json()["products"][0]["name"], "Milk")
        self.assertEqual(self.client.patch(detail, {"barcodes": ["003", "004"]}, format="json").status_code, 400)
        edit = self.client.patch(detail, {"notes": "Updated"}, format="json")
        self.assertEqual(edit.status_code, 200)
        self.assertEqual(edit.json()["notes"], "Updated")
        self.assertEqual(edit.json()["barcodes"], self.codes)
        self.assertEqual(self.client.delete(detail).status_code, 204)
        self.assertEqual(self.client.get(detail).status_code, 404)

    def test_saved_records_are_private_and_browser_writes_require_csrf(self):
        obj = SavedComparison.objects.create(user=self.owner, **self.payload)
        detail = reverse("comparison_api:saved_detail", args=[obj.pk])
        self.assertEqual(self.client.get(self.saved).status_code, 403)
        self.assertEqual(self.client.post(self.saved, self.payload, format="json").status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.saved).json(), [])
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.patch(detail, {"name": "Changed"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(detail).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.delete(detail, HTTP_ORIGIN="https://example.org").status_code, 403)
        self.assertTrue(SavedComparison.objects.filter(pk=obj.pk).exists())
