DEFAULT_DIET = 'none'

DIETS = [
    ('none', 'No preference', '', ''),
    ('vegetarian', 'Vegetarian', 'vegetarian', ''),
    ('vegan', 'Vegan', 'vegan', ''),
    ('pescatarian', 'Pescatarian', 'pescetarian', ''),
    ('ketogenic', 'Ketogenic', 'ketogenic', ''),
    ('halal', 'Halal', '', 'Skips pork and alcohol'),
]

DIET_CHOICES = [(key, label) for key, label, _, _ in DIETS]
DIET_LABELS = {key: label for key, label, _, _ in DIETS}
DIET_HELPERS = {key: helper for key, _, _, helper in DIETS if helper}
SPOONACULAR_DIETS = {key: word for key, _, word, _ in DIETS}
MAIN_DIET_ORDER = ['vegan', 'vegetarian', 'pescatarian', 'ketogenic', 'halal']

HALAL_EXCLUDE = ['pork', 'bacon', 'ham', 'wine', 'beer']
HALAL_BADGE = 'Halal not verified'
HALAL_PLAN_NOTE = 'No pork or alcohol'

ALLERGIES = [
    ('gluten', 'Gluten free', 'Gluten', 'Gluten free', ['gluten']),
    ('dairy', 'Dairy free', 'Dairy', 'Dairy free', ['dairy']),
    ('peanut', 'Peanuts', 'Peanuts', 'No peanuts', ['peanut']),
    ('tree_nut', 'Tree nuts', 'Tree nuts', 'No tree nuts', ['tree nut']),
    ('egg', 'Eggs', 'Eggs', 'No eggs', ['egg']),
    ('seafood', 'Seafood', 'Seafood', 'No seafood', ['seafood', 'shellfish']),
    ('soy', 'Soy', 'Soy', 'No soy', ['soy']),
    ('sesame', 'Sesame', 'Sesame', 'No sesame', ['sesame']),
]

ALWAYS_SHOWN_ALLERGIES = ['gluten', 'dairy', 'peanut', 'tree_nut', 'egg', 'seafood', 'soy']

ALLERGY_CHOICES = [(key, chip) for key, chip, _, _, _ in ALLERGIES]
ALLERGY_CHIPS = {key: chip for key, chip, _, _, _ in ALLERGIES}
ALLERGY_NAMES = {key: name for key, _, name, _, _ in ALLERGIES}
ALLERGY_BADGES = {key: badge for key, _, _, badge, _ in ALLERGIES}
ALLERGY_WORDS = {key: words for key, _, _, _, words in ALLERGIES}
ALLERGY_FROM_WORD = {word: key for key, _, _, _, words in ALLERGIES for word in words}

SLOTS = ['breakfast', 'lunch', 'dinner']
SNACK = 'snack'
SLOT_ORDER = SLOTS + [SNACK]
SLOT_CHOICES = [(slot, slot.capitalize()) for slot in SLOT_ORDER]
SEARCH_TYPES = {
    'breakfast': 'breakfast',
    'lunch': 'main course',
    'dinner': 'main course',
    'snack': 'snack',
}

MEAL_FILTER_CHOICES = [
    ('', 'Any meal'),
    ('breakfast', 'Breakfast'),
    ('lunch', 'Lunch'),
    ('dinner', 'Dinner'),
    ('snack', 'Snack'),
]

WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

MIN_DAYS = 1
MAX_DAYS = 14
DEFAULT_DAYS = 7
MIN_CALORIES = 1000
MAX_CALORIES = 5000
DEFAULT_CALORIES = 2000
SNACK_SHARE = 0.1
SWAP_CANDIDATES = 6
SWAP_OPTIONS = 3
RECIPES_PER_PAGE = 8
MAX_RECIPE_PAGES = 10
