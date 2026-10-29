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

    # Existing meal plans can be opened but are not removable bookmarks.
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
                "remove_url": None,
            })

    # Saved Meal of the Day records.
    if category in ("all", "meal"):
        try:
            from food_of_the_day.models import SavedMeal
            for record in SavedMeal.objects.filter(user=user).select_related("meal"):
                meal_date = record.meal.date.strftime("%B %d, %Y") if record.meal else "Featured"
                items.append({
                    "title": record.recipe_title or f"Meal of the Day ({meal_date})",
                    "type": "Meal",
                    "metadata": f"Featured {meal_date}" if record.meal else "Meal of the Day",
                    "created_at": record.created_at,
                    "open_url": reverse(
                        "food_of_the_day:detail",
                        args=[record.meal.pk],
                    ) if record.meal else reverse("food_of_the_day:index"),
                    "remove_url": reverse(
                        "profile_saved_remove",
                        args=["meal", record.pk],
                    ),
                })
        except Exception:
            pass

    # Display the newest persisted records first.
    return sorted(
        items,
        key=lambda item: item["created_at"],
        reverse=True,
    )