from profiles.models import Profile

# Strips 'none' from the diet choices so it isn't rendered as a clickable filter option
DIET_CHOICES = [(value, label) for value, label in Profile.DIET_CHOICES if value != "none"]

# Maps internal allergy names to external API tags (OpenFoodFacts='off', Spoonacular='spoon')
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

# Generates tuples for the form choices dynamically based on the map above
ALLERGY_CHOICES = [(value, value) for value in ALLERGY_MAP]

# Helper: Cleans up user input by handling strings/lists, removing invalid entries, and deduplicating
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

        # Only add valid items that aren't already in the list
        if normalized and normalized not in result:
            result.append(normalized)

    return result

# Wrapper to safely parse diet values using DIET_CHOICES
def normalize_diets(value):
    return normalize_selection(value, DIET_CHOICES)

# Wrapper to safely parse allergy values using ALLERGY_CHOICES
def normalize_allergies(value):
    return normalize_selection(value, ALLERGY_CHOICES)