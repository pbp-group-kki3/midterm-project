# fetch data from openfoodfacts API

import os # used to read .env variables
import re # change: checks that a barcode is only digits
import hashlib # change: turns any search text into a short, safe cache key
from django.utils.html import strip_tags # change: removes HTML tags from what users type (same as Aryan's module)
import requests # library used to make HTTP calls to the API
from django.core.cache import cache # implement cache by using django's short term memory - to not repeat API calls
from main.services.grading import spoonfeed_grade # import spoonfeed grade

# root address of open food facts API (indonesia focused)
BASE_URL = "https://id.openfoodfacts.org"

# headers for every request
HEADERS = {"User-Agent": os.environ.get("OFF_USER_AGENT", "SpoonFed/1.0")}

# change: input safety helpers (step 1)
BARCODE_PATTERN = re.compile(r"\d{1,32}")   # change: barcodes are digits only, at most 32 (same as the model's max_length)
MAX_QUERY_LENGTH = 100                       # change: longer searches are cut, nobody types a 100+ letter product name


# change: True only for a digits-only barcode. The barcode goes into the API URL,
# so "../" or other characters must never get that far
def is_valid_barcode(barcode):
    return isinstance(barcode, str) and BARCODE_PATTERN.fullmatch(barcode) is not None


# change: cleans what the user typed: no HTML tags, no double spaces, max 100 characters
def clean_query(text):
    text = strip_tags(text or "")
    text = " ".join(text.split())       # change: split() + join squeezes every run of spaces into one
    return text[:MAX_QUERY_LENGTH]


# change: a cache key without spaces or odd characters ("susu uht" made Django warn).
# md5 is only used as a short fingerprint here, not for security
def cache_key(prefix, text):
    return f"off:{prefix}:" + hashlib.md5(text.encode("utf-8")).hexdigest()

# product fields SpoonFeed needs the data for
FIELDS = "code,product_name,brands,quantity,image_front_small_url,nutriscore_grade,ecoscore_grade,ecoscore_score,nova_group,labels_tags,allergens_tags,categories_tags,ingredients_analysis_tags"


# Backup search service (Open Food Facts "search-a-licious").
# Used only when the normal search fails, e.g. the 503 "too busy" error. It answers with "hits" instead of "products"
BACKUP_SEARCH_URL = "https://search.openfoodfacts.org/search"

# change: step 3a, what happens when Open Food Facts is down
STALE_SECONDS = 60 * 60 * 24 * 7   # change: the "last good copy" of every answer is kept for 7 days
DOWN_KEY = "off:down"              # change: cache flag that means "the API just failed, leave it alone for now"
DOWN_SECONDS = 90                  # change: how long we leave it alone (like Aryan's negative caching)


# change: a normal list with one extra label. It means "these results were saved earlier, the API is down".
# Everyone who uses the results (views, Alyssa's comparison) still just sees a list
class StaleList(list):
    stale = True


# change: True when the results are a saved copy, used by the view to show the note
def is_stale(results):
    return getattr(results, "stale", False)


# change: remember an answer twice: the normal short cache, plus a long "last good copy" for bad days
def remember(key, value, seconds):
    cache.set(key, value, seconds)
    cache.set(key + ":last-good", value, STALE_SECONDS)


def last_good(key):
    return cache.get(key + ":last-good")


# change: one place that calls the API and catches EVERY kind of failure:
# no network, timeout, HTTP error (raise_for_status), an answer that isn't JSON (ValueError),
# or JSON that isn't the {"products": ...} object we expect. Returns data[field], or None when it failed
def call_api(url, params, field, default=None):
    if cache.get(DOWN_KEY):            # change: it failed less than 90 s ago: don't even try
        return None
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)   # 10 s max, the page never hangs
        response.raise_for_status()    # HTTP errors (404, 503...) become exceptions
        data = response.json()         # change: raises ValueError when the answer isn't JSON
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict):     # change: JSON, but not the shape we expect
        return None
    return data.get(field, default)


# change: called when both the main API and the backup failed: remember that it's down for 90 s
def mark_down():
    cache.set(DOWN_KEY, True, DOWN_SECONDS)


# helper : ask the backup search service. Returns a list of products, or None if it fails too
def backup_search(query, sort_by=None):
    params = {
        "q": f'{query} countries_tags:"en:indonesia"'.strip(),  # same Indonesia-only rule as BASE_URL
        "page_size": 24,
        "fields": FIELDS,
    }
    if sort_by:
        params["sort_by"] = sort_by                             # e.g. "-unique_scans_n" = most scanned first
    return call_api(BACKUP_SEARCH_URL, params, "hits", default=[])   # change: same failure handling as the main API


# change: the shared ending for search and browse: fresh answer -> remember it,
# both APIs failed -> mark the API as down and hand back the last good copy (or None if there is none)
def finish(key, products, seconds):
    if products is not None:
        remember(key, products, seconds)
        return products
    mark_down()
    saved = last_good(key)
    return StaleList(saved) if saved is not None else None


# helper function
def get_score(product):
    return product["spoonfeed"]["score"]

# return one product as a dict, or none if it's missing/API fails
# function : get product and it's detail from the API
def get_product(barcode):
    if not is_valid_barcode(barcode):    # change: refuse anything that isn't a real barcode, before calling the API
        return None
    key = f"off:product:{barcode}"
    product = cache.get(key)
    if product is not None: # if something is in the cache, return product
        return product

    if cache.get(DOWN_KEY):              # change: API marked as down: go straight to the saved copy
        return last_good(key)
    try:
        response = requests.get( # sends a GET request and the result stored in variable response
            f"{BASE_URL}/api/v2/product/{barcode}", # address of the product
            params={"fields": FIELDS + ",nutriments,nutrient_levels,ingredients_text,ecoscore_data"}, # details needed for the product, FIELDS - from API
            headers=HEADERS, # send User-Agent
            timeout=10, # after 10 sec, give up (page doesn't hang)
        )
        response.raise_for_status() # if there's an HTTP error, it'll be turned into an exception
        data = response.json() # parse JSON
    except (requests.RequestException, ValueError): # change: network / HTTP error / not JSON
        mark_down()
        return last_good(key)            # change: the last good copy, or None if we never had one
    if not isinstance(data, dict):
        mark_down()
        return last_good(key)

    product = data.get("product") # take just the product part. None = the product doesn't exist (not a failure)
    if product is not None:
        remember(key, product, 60 * 60 * 6) # store the product for 6 hrs ( 60 sec * 60 min * 6), plus the last good copy
    return product # return product dict to caller

# returns a list of products matching text, [] if none, or None if API fails
# change: when the API is down it returns the last good copy as a StaleList (see is_stale)
# function : to search products in the search bar
def search_products(text):
    text = clean_query(text).lower() # change: cleaned first (tags, spaces, length), then lower case for easier caching

    key = cache_key("search", text)     # change: safe key, e.g. off:search:3f2a... instead of off:search:susu uht
    products = cache.get(key)
    if products is not None:
        return products

    products = call_api(
        f"{BASE_URL}/cgi/search.pl",
        {
            "search_terms": text,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": 24,
            "fields": FIELDS,
        },
        "products",
        default=[],
    )
    if products is None:
        products = backup_search(text) # normal search failed (e.g. 503): try the backup service
    return finish(key, products, 60 * 60)   # change: cache it, or fall back to the last good copy

# returns popular Indonesian products (most scanned first), [] if none, or None if the API fails
# function : what the Discover page shows before anything is searched
def browse_products():
    key = "off:browse"                     # one cache entry: the same list for everyone
    products = cache.get(key)
    if products is not None:
        return products

    products = call_api(
        f"{BASE_URL}/cgi/search.pl",
        {
            "action": "process",
            "json": 1,
            "page_size": 24,
            "sort_by": "unique_scans_n",   # most scanned = most popular
            "fields": FIELDS,
        },                                 # no search_terms: all products sold in Indonesia
        "products",
        default=[],
    )
    if products is None:
        products = backup_search("", sort_by="-unique_scans_n")   # normal search failed: try the backup
    return finish(key, products, 60 * 60)

# function : give alternative option based on the current clicked product, recommends another product (up to 3)
# if no alternative, returns []
def get_alternatives(product, limit=3):
    categories = product.get("categories_tags") or []
    if not categories:
        return []
    category = categories[-1]

    current_grade = spoonfeed_grade(product)["grade"] # gives the grade (A, B, ...)
    if current_grade == "?":
        return []

    key = f"off:category:{category}" # one cache entry per category
    candidates = cache.get(key) # look for candidates inside cache first
    if candidates is None:
        candidates = call_api(               # change: same failure handling as search
            f"{BASE_URL}/api/v2/search",
            {"categories_tags": category, "fields": FIELDS, "page_size": 24},
            "products",
            default=[],
        )
        if candidates is None:
            candidates = backup_search(f'categories_tags:"{category}"') # normal search failed: try the backup
        candidates = finish(key, candidates, 60 * 60)   # change: or the last good copy for this category
        if candidates is None:
            return []

    alternatives = []
    for p in candidates:
        if p.get("code") == product.get("code"): # if p is the current product
            continue
        result = spoonfeed_grade(p)
        if result["grade"] != "?" and result["grade"] < current_grade:
            p["spoonfeed"] = result
            alternatives.append(p)

    alternatives.sort(key=get_score, reverse=True)
    return alternatives[:limit]