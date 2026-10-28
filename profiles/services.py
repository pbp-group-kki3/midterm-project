# IMPORTS
from django.core.exceptions import ObjectDoesNotExist

# PREFERENCES HELPER
def get_preferences(user):
    # DEFAULT PREFERENCES
    default_prefs = {
        'diet': 'none',
        'allergies': [],
        'off_tags': [],
        'spoonacular_intolerances': [],
        'exclude_ingredients': ''
    }

    # AUTHENTICATION CHECK
    if not user.is_authenticated:
        return default_prefs

    # PROFILE RETRIEVAL
    try:
        profile = user.profile
    except ObjectDoesNotExist:
        return default_prefs

    # DIET AND ALLERGIES DATA
    diet = profile.diet
    allergies = profile.allergies if isinstance(profile.allergies, list) else []

    # ALLERGY MAP
    allergy_map = {
        'Milk': {'off': 'en:milk', 'spoon': 'dairy'},
        'Peanuts': {'off': 'en:peanuts', 'spoon': 'peanut'},
        'Gluten': {'off': 'en:gluten', 'spoon': 'gluten'},
        'Soy': {'off': 'en:soybeans', 'spoon': 'soy'},
        'Eggs': {'off': 'en:eggs', 'spoon': 'egg'},
        'Fish': {'off': 'en:fish', 'spoon': 'seafood'},
        'Shellfish': {'off': 'en:crustaceans', 'spoon': 'shellfish'},
        'Sesame': {'off': 'en:sesame-seeds', 'spoon': 'sesame'},
        'Tree nuts': {'off': 'en:nuts', 'spoon': 'tree nut'},
    }

    # TAG EXTRACTION
    off_tags = []
    spoon_intolerances = []

    for allergy in allergies:
        if allergy in allergy_map:
            off_tags.append(allergy_map[allergy]['off'])
            spoon_intolerances.append(allergy_map[allergy]['spoon'])

    # HALAL EXCLUSIONS
    exclude_ingredients = ''
    if diet == 'halal':
        exclude_ingredients = 'pork,bacon,ham,wine,beer'

    # RETURN DATA
    return {
        'diet': diet,
        'allergies': allergies,
        'off_tags': off_tags,
        'spoonacular_intolerances': spoon_intolerances,
        'exclude_ingredients': exclude_ingredients
    }