# IMPORTS
from django.core.exceptions import ObjectDoesNotExist
from profiles.preferences import (
    ALLERGY_MAP,
    normalize_allergies,
    normalize_diets,
)

# PREFERENCES HELPER
def get_preferences(user):
    # DEFAULT PREFERENCES
    defaults = {
        "diet": [],
        "allergies": [],
        "off_tags": [],
        "spoonacular_intolerances": [],
        "exclude_ingredients": "",
    }

    # AUTHENTICATION CHECK
    if not user.is_authenticated:
        return defaults

    # PROFILE RETRIEVAL
    try:
        profile = user.profile
    except ObjectDoesNotExist:
        return defaults

    # DIET AND ALLERGIES DATA
    diets = normalize_diets(profile.diet)
    allergies = normalize_allergies(profile.allergies)

    # Convert selected allergies to Open Food Facts tags.
    off_tags = list(dict.fromkeys(
        ALLERGY_MAP[allergy]["off"]
        for allergy in allergies
    ))

    # Convert selected allergies to Spoonacular intolerance values.
    spoon_intolerances = list(dict.fromkeys(
        ALLERGY_MAP[allergy]["spoon"]
        for allergy in allergies
    ))

    # RETURN DATA
    return {
        "diet": diets,
        "allergies": allergies,
        "off_tags": off_tags,
        "spoonacular_intolerances": spoon_intolerances,
        "exclude_ingredients": (
            "pork,bacon,ham,wine,beer"
            if "halal" in diets
            else ""
        ),
    }