# IMPORTS
from django.core.exceptions import ObjectDoesNotExist
from profiles.preferences import (
    ALLERGY_MAP,
    normalize_allergies,
    normalize_diets,
)

# HELPER: Extracts user preferences and maps them to external API requirements
def get_preferences(user):
    # Returns safe empty defaults if the user isn't logged in
    defaults = {
        "diet": [],
        "allergies": [],
        "off_tags": [],
        "spoonacular_intolerances": [],
        "exclude_ingredients": "",
    }

    # Stop early if not authenticated
    if not user.is_authenticated:
        return defaults

    # Safely fetch the profile
    try:
        profile = user.profile
    except ObjectDoesNotExist:
        return defaults

    # Clean stored diets and allergies
    diets = normalize_diets(profile.diet)
    allergies = normalize_allergies(profile.allergies)

    # Convert allergy list to Open Food Facts (OFF) tags using the ALLERGY_MAP
    off_tags = list(dict.fromkeys(
        ALLERGY_MAP[allergy]["off"]
        for allergy in allergies
    ))

    # Convert allergy list to Spoonacular tags using the ALLERGY_MAP
    spoon_intolerances = list(dict.fromkeys(
        ALLERGY_MAP[allergy]["spoon"]
        for allergy in allergies
    ))

    # Package and return mapped preferences
    return {
        "diet": diets,
        "allergies": allergies,
        "off_tags": off_tags,
        "spoonacular_intolerances": spoon_intolerances,
        # Adds specific ingredient exclusion rules based on the 'halal' diet tag
        "exclude_ingredients": (
            "pork,bacon,ham,wine,beer"
            if "halal" in diets
            else ""
        ),
    }