from django.urls import reverse

from comparison.models import SavedComparison
from main.models import FavoriteProduct
from meal_plan.models import MealPlan


# Define the categories supported by the Saved filter links.
SAVED_CATEGORIES = (
    ("all", "All"),
    ("product", "Products"),
    ("comparison", "Comparisons"),
    ("article", "Articles"),
    ("meal-plan", "Meal plans"),
    ("meal", "Meals"),
)


# Prepare owned persisted records for the shared Saved row template.
def saved_items(user, category):
    items = []

    # Product removal deletes the favorite record rather than product data.
    if category in ("all", "product"):
        for record in FavoriteProduct.objects.filter(user=user):
            items.append({
                "title": record.product_name or record.barcode,
                "type": "Product",
                "metadata": f"Barcode {record.barcode}",
                "created_at": record.created_at,
                "open_url": reverse(
                    "main:product_detail",
                    args=[record.barcode],
                ),
                "remove_url": reverse(
                    "profile_saved_remove",
                    args=["product", record.pk],
                ),
            })

    # Reuse the existing SavedComparison model.
    if category in ("all", "comparison"):
        for record in SavedComparison.objects.filter(user=user):
            items.append({
                "title": record.name,
                "type": "Comparison",
                "metadata": (
                    f"{len(record.barcodes)} products"
                    + (f" · {record.notes}" if record.notes else "")
                ),
                "created_at": record.created_at,
                "open_url": reverse(
                    "profile_saved_comparison",
                    args=[record.pk],
                ),
                "remove_url": reverse(
                    "profile_saved_remove",
                    args=["comparison", record.pk],
                ),
            })

    if category in ("all", "meal-plan"):
        for record in MealPlan.objects.filter(user=user):
            items.append({
                "title": record.name,
                "type": "Meal plan",
                "metadata": f"{record.days_label} · {record.calorie_label}",
                "created_at": record.created_at,
                "open_url": reverse(
                    "meal_plan:plan_detail",
                    args=[record.pk],
                ),
                "remove_url": reverse(
                    "profile_saved_remove",
                    args=["meal-plan", record.pk],
                ),
                "confirm_title": "Delete this plan?",
                "confirm_text": f"“{record.name}” and its {record.days_label} of meals will be removed. This can't be undone.",
                "confirm_label": "Delete plan",
            })

    # Display the newest persisted records first.
    return sorted(
        items,
        key=lambda item: item["created_at"],
        reverse=True,
    )