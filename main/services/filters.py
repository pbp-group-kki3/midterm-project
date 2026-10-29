# SpoonFeed filters: keep only the products that pass the chosen filters.
# Pure Python, no API calls: it filters the cached search results (team rule)

# Allergy word in the URL -> Open Food Facts tag (from the team doc's allergy table)
ALLERGEN_TAGS = {
    "milk": "en:milk",
    "peanuts": "en:peanuts",
    "gluten": "en:gluten",
    "soy": "en:soybeans",
}

# Label word in the URL -> (which list to look in, the tag that must be there)
LABEL_RULES = {
    "halal": ("labels_tags", "en:halal"),
    "organic": ("labels_tags", "en:organic"),
    "vegan": ("ingredients_analysis_tags", "en:vegan"),
    "vegetarian": ("ingredients_analysis_tags", "en:vegetarian"),
    "palm_oil_free": ("ingredients_analysis_tags", "en:palm-oil-free"),
}


# True if the product passes every chosen filter. Needs product["spoonfeed"] (from prepare_card)
def passes_filters(product, grades, labels, processing, avoid):
    # Grade: the SpoonFeed letter must be one of the chosen ones, e.g. ["A", "B"]
    if grades and product["spoonfeed"]["grade"] not in grades:
        return False

    # Labels and diet: every chosen label must be present
    for label in labels:
        rule = LABEL_RULES.get(label)
        if rule is None:                                   # unknown word in the URL: ignore it
            continue
        field, tag = rule
        if tag not in (product.get(field) or []):          # "or []" so a missing list can't crash
            return False

    # Processing: "Not ultra-processed" = NOVA 1, 2 or 3. Missing NOVA can't be verified, so it's hidden
    if processing == "not_ultra" and product.get("nova_group") not in (1, 2, 3):
        return False

    # Avoid allergens: drop products that list the allergen.
    # An empty allergens list means "unknown", not "allergen-free", so those products stay
    allergen_tags = product.get("allergens_tags") or []
    for allergen in avoid:
        tag = ALLERGEN_TAGS.get(allergen)
        if tag and tag in allergen_tags:
            return False

    return True


# Sort key for "Sort: Best grade": highest SpoonFeed score first, products without a grade last
def best_grade_key(product):
    score = product["spoonfeed"]["score"]
    return score if score is not None else -1


# Diet -> (list to look in, tag that confirms it, tag that rules it out). Halal has no "not halal" tag
DIET_RULES = {
    "halal": ("labels_tags", "en:halal", None),
    "vegan": ("ingredients_analysis_tags", "en:vegan", "en:non-vegan"),
    "vegetarian": ("ingredients_analysis_tags", "en:vegetarian", "en:non-vegetarian"),
}


# The "Fits your preferences" chip. prefs comes from Serafin's get_preferences(user).
# Returns None (no chip), or {"status": "fits" / "unknown" / "conflict", "text": "..."}
# Only says "fits" when the product's data CONFIRMS it; missing data gives "unknown", never "fits"
def preference_fit(product, prefs):
    if not prefs:
        return None

    # Support current list values and older single-string values.
    raw_diets = prefs.get("diet") or []

    if isinstance(raw_diets, str):
        raw_diets = [raw_diets]

    if not isinstance(raw_diets, list):
        raw_diets = []

    diets = list(dict.fromkeys(
        value.strip().lower()
        for value in raw_diets
        if isinstance(value, str)
        and value.strip()
        and value.strip().lower() != "none"
    ))

    allergy_tags = prefs.get("off_tags") or []              # e.g. ["en:milk"]
    if not diets and not allergy_tags:
        return None                                         # no preferences set: nothing to compare

    # 1. Allergens: a listed allergen is a clear conflict
    allergens = product.get("allergens_tags") or []
    for tag in allergy_tags:
        if tag in allergens:
            return {"status": "conflict", "text": "Contains " + tag.split(":")[-1]}   # "en:milk" -> "milk"

    # 2. Diet
    unverified_diets = []
    for diet in diets:
        rule = DIET_RULES.get(diet)
        if rule is None:                                    # pescatarian: Open Food Facts has no tag for it
            unverified_diets.append(diet)
            continue
        field, yes_tag, no_tag = rule
        tags = product.get(field) or []
        if no_tag and no_tag in tags:
            return {"status": "conflict", "text": f"Not {diet}"}
        if yes_tag not in tags:
            unverified_diets.append(diet)

    if unverified_diets:
        return {
            "status": "unknown",
            "text": "? Can't verify " + ", ".join(unverified_diets),
        }
    # 3. Allergies set but the product lists no allergens at all: that means unknown, not allergen-free
    if allergy_tags and not allergens:
        return {"status": "unknown", "text": "? Can't verify allergens"}

    return {"status": "fits", "text": "\u2713 Fits your preferences"}

