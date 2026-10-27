import math

# === SCORES ===
def normalize_grade(value):
    if not isinstance(value, str):
        return None

    grade = value.strip().lower()
    return grade if grade in "abcde" and len(grade) == 1 else None


def normalize_nova(value):
    number = get_numeric_value(value)

    if number in (1, 2, 3, 4):
        return int(number)

    return None


def build_ranked_cells(displays, ranks):
    best_rank = None

    if (
        len(ranks) >= 2
        and all(rank is not None for rank in ranks)
        and len(set(ranks)) > 1
    ):
        best_rank = min(ranks)

    return [
        {
            "display": display,
            "is_better": best_rank is not None and rank == best_rank,
        }
        for display, rank in zip(displays, ranks)
    ]


def build_score_rows(products):
    rows = [
        {
            "label": "SpoonFeed grade",
            "cells": [
                {"display": "?", "is_better": False}
                for product in products
            ],
        },
    ]

    grade_ranks = {
        "a": 1,
        "b": 2,
        "c": 3,
        "d": 4,
        "e": 5,
    }

    for label, field in [
        ("Nutri-Score", "nutriscore_grade"),
        ("Green-Score", "ecoscore_grade"),
    ]:
        grades = [
            normalize_grade(product.get(field))
            for product in products
        ]

        displays = [
            grade.upper() if grade else "Not available"
            for grade in grades
        ]

        ranks = [grade_ranks.get(grade) for grade in grades]

        rows.append({
            "label": label,
            "cells": build_ranked_cells(displays, ranks),
        })

    nova_values = [
        normalize_nova(product.get("nova_group"))
        for product in products
    ]

    rows.append({
        "label": "Processing (NOVA)",
        "cells": build_ranked_cells(
            [
                str(value) if value is not None else "Not available"
                for value in nova_values
            ],
            nova_values,
        ),
    })

    return rows


def format_tags(tags):
    if not isinstance(tags, list):
        return "Not available"

    names = []

    for tag in tags:
        if not isinstance(tag, str):
            continue

        name = tag.split(":", 1)[-1].replace("-", " ").strip()

        if name and name not in names:
            names.append(name)

    return ", ".join(names) if names else "Not available"


def build_label_rows(products):
    return [
        {
            "label": label,
            "cells": [
                {
                    "display": format_tags(product.get(field)),
                    "is_better": False,
                }
                for product in products
            ],
        }
        for label, field in [
            ("Labels", "labels_tags"),
            ("Allergens", "allergens_tags"),
        ]
    ]

# === NUTRITIONS ===
NUTRIENT_RULES = [
    ("Energy", "energy-kcal_100g", "kcal", "lower"),
    ("Fat", "fat_100g", "g", "lower"),
    ("Saturated fat", "saturated-fat_100g", "g", "lower"),
    ("Sugars", "sugars_100g", "g", "lower"),
    ("Protein", "proteins_100g", "g", "higher"),
    ("Fiber", "fiber_100g", "g", "higher"),
    ("Salt", "salt_100g", "g", "lower"),
]


def get_numeric_value(value):
    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number) or number < 0:
        return None

    return number


def build_nutrition_rows(products):
    rows = []

    for label, field, unit, direction in NUTRIENT_RULES:
        values = []

        for product in products:
            nutriments = product.get("nutriments") or {}
            value = get_numeric_value(nutriments.get(field))
            values.append(value)

        best_value = None

        if (
            len(values) >= 2
            and all(value is not None for value in values)
            and len(set(values)) > 1
        ):
            if direction == "lower":
                best_value = min(values)
            else:
                best_value = max(values)

        cells = []

        for value in values:
            cells.append({
                "display": (
                    f"{value:.2f}".rstrip("0").rstrip(".") + f" {unit}"
                    if value is not None
                    else "Not available"
                ),
                "is_better": (
                    best_value is not None and value == best_value
                ),
            })

        rows.append({
            "label": label,
            "cells": cells,
        })

    return rows