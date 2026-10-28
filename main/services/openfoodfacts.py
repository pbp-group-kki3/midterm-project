# fetch data from openfoodfacts API

import os # used to read .env variables
import requests # library used to make HTTP calls to the API
from django.core.cache import cache # implement cache by using django's short term memory - to not repeat API calls
from main.services.grading import spoonfeed_grade # import spoonfeed grade

# root address of open food facts API (indonesia focused)
BASE_URL = "https://id.openfoodfacts.org"

# headers for every request
HEADERS = {"User-Agent": os.environ.get("OFF_USER_AGENT", "SpoonFed/1.0")}

# product fields SpoonFeed needs the data for
FIELDS = "code,product_name,brands,quantity,image_front_small_url,nutriscore_grade,ecoscore_grade,ecoscore_score,nova_group,labels_tags,allergens_tags,categories_tags,ingredients_analysis_tags"

# helper function
def get_score(product):
    return product["spoonfeed"]["score"]

# return one product as a dict, or none if it's missing/API fails
# function : get product and it's detail from the API
def get_product(barcode):
    key = f"off:product:{barcode}"
    product = cache.get(key)
    if product is not None: # if something is in the cache, return product
        return product

    try: 
        response = requests.get( # sends a GET request and the result stored in variable response
            f"{BASE_URL}/api/v2/product/{barcode}", # address of the product
            params={"fields": FIELDS + ",nutriments,ingredients_text,ecoscore_data"}, # details needed for the product, FIELDS - from API
            headers=HEADERS, # send User-Agent
            timeout=10, # after 10 sec, give up (page doesn't hang)
        )
        response.raise_for_status() # if there's an HTTP error, it'll be turned into an exception
        product = response.json().get("product") # parse JSON, to take just the product part
    except requests.RequestException: # network / HTTP error goes here
        return None

    cache.set(key, product, 60 * 60 * 6) # store the product for 6 hrs ( 60 sec * 60 min * 6)
    return product # return product dict to caller

# returns a list of products matching text, [] if none, or None if API fails
# function : to search products in the search bar
def search_products(text):
    text = text.strip().lower() # turns into lower case for easier caching

    key = f"off:search:{text}"
    products = cache.get(key)
    if products is not None:
        return products

    try: 
        response = requests.get(
            f"{BASE_URL}/cgi/search.pl",
            params={
                "search_terms":text, 
                "search_simple":1,
                "action":"process",
                "json":1,
                "page_size":24,
                "fields":FIELDS},
            headers=HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        products = response.json().get("products", [])
    except requests.RequestException:
        return None
    cache.set(key, products, 60 * 60)
    return products

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
        try:
            response = requests.get(
                f"{BASE_URL}/api/v2/search",
                params={
                    "categories_tags" : category,
                    "fields" : FIELDS,
                    "page_size" : 24
                },
                headers=HEADERS,
                timeout=10,
            )
            response.raise_for_status()
            candidates = response.json().get("products",[])
        
        except requests.RequestException:
            return[]
        cache.set(key, candidates, 60 * 60)

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