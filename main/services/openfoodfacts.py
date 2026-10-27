# fetch data from openfoodfacts API

import os # used to read .env variables
import requests # library used to make HTTP calls to the API
from django.core.cache import cache # implement cache by using django's short term memory - to not repeat API calls

# root address of open food facts API (indonesia focused)
BASE_URL = "https://id.openfoodfacts.org"

# headers for every request
HEADERS = {"User-Agent": os.environ.get("OFF_USER_AGENT", "SpoonFed/1.0")}

# product fields SpoonFeed needs the data for
FIELDS = "code,product_name,brands,quantity,image_front_small_url,nutriscore_grade,ecoscore_grade,ecoscore_score,nova_group,labels_tags,allergens_tags,categories_tags,ingredients_analysis_tags"

# return one product as a dict, or none if it's missing/API fails
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