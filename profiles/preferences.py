from profiles.models import Profile

# Reuse the model's allowed diets without a separate None selection.
DIET_CHOICES = [(value, label) for value, label in Profile.DIET_CHOICES if value != "none"]

# Map profile allergy labels to product and recipe API values.
ALLERGY_MAP = {
    "Milk": {"off": "en:milk", "spoon": "dairy"},
    "Peanuts": {"off": "en:peanuts", "spoon": "peanut"},
    "Gluten": {"off": "en:gluten", "spoon": "gluten"},
    "Soy": {"off": "en:soybeans", "spoon": "soy"},
    "Eggs": {"off": "en:eggs", "spoon": "egg"},
    "Fish": {"off": "en:fish", "spoon": "seafood"},
    "Shellfish": {"off": "en:crustaceans", "spoon": "shellfish"},
    "Sesame": {"off": "en:sesame-seeds", "spoon": "sesame"},
    "Tree nuts": {"off": "en:nuts", "spoon": "tree nut"},
}

# Use the same allowed allergy choices in signup and preferences.
ALLERGY_CHOICES = [(value, value) for value in ALLERGY_MAP]

# Convert supported legacy strings and current lists into unique allowed values.
def normalize_selection(value, choices):
    if isinstance(value, str):
        value = value.split(",")

    if not isinstance(value, list):
        return []

    allowed = {
        key.casefold(): key
        for key, label in choices
    }
    result = []

    for item in value:
        if not isinstance(item, str):
            continue

        normalized = allowed.get(item.strip().casefold())

        if normalized and normalized not in result:
            result.append(normalized)

    return result

# Normalize stored diet preferences without changing the database.
def normalize_diets(value):
    return normalize_selection(value, DIET_CHOICES)

# Normalize stored allergy preferences without changing the database.
def normalize_allergies(value):
    return normalize_selection(value, ALLERGY_CHOICES)