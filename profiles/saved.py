from django.urls import reverse

from comparison.models import SavedComparison
from main.models import FavoriteProduct
from blog.models import SavedArticle

# Valid categories for filtering the Saved items page
SAVED_CATEGORIES = (
    ("all", "All"),
    ("product", "Products"),
    ("comparison", "Comparisons"),
    ("article", "Articles"),
    ("meal", "Meals"),
)

# Helper: Aggregates different data models (Products, Comparisons, Meals, Articles) into one standard list structure for the frontend
def saved_items(user, category):
    items = []

    # Map FavoriteProduct records to the standard dictionary format
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
                ) + "?source=saved",
                "remove_url": reverse(
                    "profile_saved_remove",
                    args=["product", record.pk],
                ),
            })

    # Map SavedComparison records to the standard dictionary format
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

    # Map SavedMeal records, using snapshot metadata if the original meal is missing
    if category in ("all", "meal"):
        try:
            from food_of_the_day.models import SavedMeal
            for record in SavedMeal.objects.filter(user=user).select_related("meal"):
                snapshot = record.snapshot_data or {}
                meal_date = record.meal.date.strftime("%B %d, %Y") if record.meal else None

                title = record.recipe_title or snapshot.get("title")
                if not title and meal_date:
                    title = f"Meal of the Day ({meal_date})"
                elif not title:
                    title = "Saved Meal"

                meta_parts = []
                if meal_date:
                    meta_parts.append(f"Featured {meal_date}")
                calories = snapshot.get("calories")
                if calories:
                    meta_parts.append(f"{calories} kcal")
                ready_in = snapshot.get("ready_in_minutes") or snapshot.get("readyInMinutes")
                if ready_in:
                    meta_parts.append(f"{ready_in} min")

                metadata = " · ".join(meta_parts) if meta_parts else "Meal of the Day"

                items.append({
                    "title": title,
                    "type": "Meal",
                    "metadata": metadata,
                    "created_at": record.created_at,
                    "open_url": reverse(
                        "food_of_the_day:detail",
                        args=[record.meal.pk],
                    ) + "?source=saved" if record.meal else reverse("food_of_the_day:index"),
                    "remove_url": reverse(
                        "profile_saved_remove",
                        args=["meal", record.pk],
                    ),
                })
        except Exception:
            pass

    # Map SavedArticle records to the standard dictionary format
    if category in ("all", "article"):
        for record in SavedArticle.objects.filter(user=user):
            snapshot = record.snapshot_data

            items.append({
                "title": snapshot.get("title", "Saved article"),
                "type": "Article",
                "metadata": (
                    snapshot.get("author_name", "Unknown author")
                    + " · "
                    + snapshot.get("topic_label", "Article")
                ),
                "created_at": record.created_at,
                "open_url": reverse(
                    "blog:saved_article_detail",
                    args=[record.pk],
                ),
                "remove_url": reverse(
                    "blog:saved_article_remove",
                    args=[record.pk],
                ),
                "can_remove_article": True,
            })

    # Sort everything chronologically so the newest saved item appears first
    return sorted(
        items,
        key=lambda item: item["created_at"],
        reverse=True,
    )