# Product detail page: turns raw Open Food Facts fields into simple rows for the template.
# Pure Python, no API calls. Matches the Figma frame "v2 / Product detail - Desktop (logged in)"
import re

from main.services.grading import grade_value, GREEN_POINTS

# (label, Open Food Facts nutriments key, unit, nutrient_levels key or None)
# Only fat, saturated fat, sugars and salt have a level in Open Food Facts, so only they can get a green dot
NUTRIENTS = [
    ("Energy", "energy-kcal_100g", "kcal", None),
    ("Fat", "fat_100g", "g", "fat"),
    ("Saturated fat", "saturated-fat_100g", "g", "saturated-fat"),
    ("Carbohydrates", "carbohydrates_100g", "g", None),
    ("Sugars", "sugars_100g", "g", "sugars"),
    ("Fiber", "fiber_100g", "g", None),
    ("Protein", "proteins_100g", "g", None),
    ("Salt", "salt_100g", "g", "salt"),
]

NOT_INDICATED = "Not indicated"   # Figma's wording for missing environment data


# 1.2 -> "1.2", 44.0 -> "44", 0.125 -> "0.125"
def number(value):
    return f"{round(float(value), 3):g}"


# "en:milk" -> "milk", "en:palm-oil" -> "palm oil"
def tag_name(tag):
    return tag.split(":")[-1].replace("-", " ")


# Bar color from the factor's points, using the same bands as the SpoonFeed letters:
# 60+ (A/B) green, 40-59 (C) amber, under 40 (D/E) red. Figma: 75 green, 40 amber, 37 red
def bar_tone(points):
    if points >= 60:
        return "success"
    if points >= 40:
        return "warning"
    return "danger"


# The 3 bars of "How the grade is built". A missing factor has no bar and is "not counted"
def build_grade_rows(product):
    parts = product["spoonfeed"]["parts"]
    tiles = product["tiles"]
    eco_score = product.get("ecoscore_score")
    green_text = eco_score if isinstance(eco_score, (int, float)) else tiles["green"]
    rows = [
        ("nutrition", f"Nutrition: Nutri-Score {tiles['nutri']}", 50),
        ("environment", f"Environment: Green-Score {green_text}", 35),
        ("processing", f"Processing: NOVA {tiles['nova']}", 15),
    ]
    result = []
    for key, label, weight in rows:
        points = parts.get(key)
        result.append({
            "label": f"{label} ({weight}% weight)" if points is not None else f"{label} (not counted)",
            "points": round(points) if points is not None else None,
            "tone": bar_tone(points) if points is not None else "",
        })
    return result


# "Nutrition per 100 ml" or "per 100 g", from the pack size. Unknown -> "100 g or ml"
def nutrition_unit(product):
    quantity = (product.get("quantity") or "").lower()
    if re.search(r"\d\s*(ml|cl|l)\b", quantity):
        return "100 ml"
    if re.search(r"\d\s*(g|kg)\b", quantity):
        return "100 g"
    return "100 g or ml"


# Rows of the Nutrition panel. good = green dot (Open Food Facts level "low"). Missing value -> "?"
def build_nutrition(product):
    nutriments = product.get("nutriments") or {}
    levels = product.get("nutrient_levels") or {}
    rows = []
    for label, key, unit, level_key in NUTRIENTS:
        value = nutriments.get(key)
        rows.append({
            "label": label,
            "value": f"{number(value)} {unit}" if isinstance(value, (int, float)) else "?",
            "good": level_key is not None and levels.get(level_key) == "low",
        })
    return rows


# Badges under the ingredients: allergens (amber), vegan status, palm oil
def build_ingredient_badges(product):
    badges = []
    for tag in product.get("allergens_tags") or []:
        badges.append({"text": "Contains " + tag_name(tag), "style": "badge-warning"})
    analysis = product.get("ingredients_analysis_tags") or []
    if "en:vegan" in analysis:
        badges.append({"text": "Vegan", "style": "badge-success"})
    elif "en:non-vegan" in analysis:
        badges.append({"text": "Non-vegan", "style": ""})
    if "en:palm-oil-free" in analysis:
        badges.append({"text": "Palm oil free", "style": "badge-success"})
    elif "en:palm-oil" in analysis:
        badges.append({"text": "Contains palm oil", "style": "badge-warning"})
    return badges


# Rows of the Environment panel, from ecoscore_data
def build_environment(product):
    data = product.get("ecoscore_data") or {}
    adjustments = data.get("adjustments") or {}

    # Green-Score: "D, 37 out of 100"
    letter = grade_value(product.get("ecoscore_grade"), GREEN_POINTS)
    score = product.get("ecoscore_score")
    if letter != "?" and isinstance(score, (int, float)):
        green = f"{letter}, {number(score)} out of 100"
    elif letter != "?":
        green = letter
    else:
        green = NOT_INDICATED

    # Carbon footprint: agribalyse co2_total is kg CO2e per kg, x 100 = grams per 100 g
    co2 = (data.get("agribalyse") or {}).get("co2_total")
    carbon = f"{round(co2 * 100)} g CO₂e per 100 g" if isinstance(co2, (int, float)) else NOT_INDICATED

    # Packaging: the materials Open Food Facts knows, e.g. "Plastic, Cardboard"
    packaging_data = adjustments.get("packaging") or {}
    materials = [tag_name(p.get("material", "")).capitalize() for p in packaging_data.get("packagings") or [] if p.get("material") and p.get("material") != "en:unknown"]   # "unknown" means not indicated
    packaging = ", ".join(dict.fromkeys(materials)) or NOT_INDICATED      # dict.fromkeys removes repeats, keeps order

    # Origin of ingredients: known countries only ("en:unknown" is skipped)
    origins_data = adjustments.get("origins_of_ingredients") or {}
    countries = [tag_name(o.get("origin", "")).title() for o in origins_data.get("aggregated_origins") or []
                 if o.get("origin") and o.get("origin") != "en:unknown"]
    origin = ", ".join(countries) or NOT_INDICATED

    return [
        {"label": "Green-Score", "value": green},
        {"label": "Carbon footprint", "value": carbon},
        {"label": "Packaging", "value": packaging},
        {"label": "Origin of ingredients", "value": origin},
    ]


# Ingredients text: Open Food Facts marks allergens with underscores ("_Oat_"); remove them for display
def clean_ingredients(product):
    text = (product.get("ingredients_text") or "").replace("_", "").strip()
    return text or None

