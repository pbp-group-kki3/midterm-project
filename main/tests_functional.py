# change: step 10. Functional tests: a real (hidden) Chrome clicks through Discover like a user would.
# The normal tests in tests.py can't run JavaScript, so HTMX, the heart and the toasts are checked here.
#
# Run them:
#   pip install -r requirements-for-selenium-test.txt
#   python manage.py test main.tests_functional
#
# They SKIP themselves (never fail) when selenium or Chrome isn't installed, or when the htmx CDN can't be reached,
# so teammates, `python manage.py test` and the deployment are not affected.
import os
import unittest
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache

from main.models import FavoriteProduct

try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    HAS_SELENIUM = True
except ImportError:                       # selenium isn't installed: every test below is skipped
    HAS_SELENIUM = False


# Fake Open Food Facts results, so the tests don't need the internet or the real API (same idea as tests.py)
PRODUCTS = [
    {
        "code": str(8990000000000 + i),
        "product_name": f"Susu Test {i}",
        "nutriscore_grade": "abcde"[i % 5],
        "ecoscore_grade": "abcde"[i % 5],
        "nova_group": 1 + i % 4,
        "quantity": "1L",
        "labels_tags": ["en:halal"],
    }
    for i in range(10)
]


def fake_search(query):
    return [dict(p) for p in PRODUCTS]    # a fresh copy every time, like the real cache


@unittest.skipUnless(HAS_SELENIUM, "selenium is not installed (pip install -r requirements-for-selenium-test.txt)")
class DiscoverBrowserTests(StaticLiveServerTestCase):
    host = "localhost"                    # must be in ALLOWED_HOSTS
    WAIT = 10                             # seconds to wait for HTMX / fetch answers

    @classmethod
    def setUpClass(cls):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")             # no window pops up
        options.add_argument("--window-size=1280,900")
        options.add_argument("--no-sandbox")
        if os.getenv("CHROME_BINARY"):                     # optional: a specific Chrome
            options.binary_location = os.getenv("CHROME_BINARY")
        service = Service(os.getenv("CHROMEDRIVER")) if os.getenv("CHROMEDRIVER") else None
        try:
            cls.browser = webdriver.Chrome(options=options, service=service)
        except WebDriverException as error:                # no Chrome on this computer
            raise unittest.SkipTest(f"Chrome could not start: {error.msg}")
        super().setUpClass()                               # starts the live test server

    @classmethod
    def tearDownClass(cls):
        cls.browser.quit()
        super().tearDownClass()

    def setUp(self):
        cache.clear()                                       # fresh rate limits, sessions and API cache
        for name in ("search_products", "browse_products"):
            patcher = patch(f"main.views.{name}", side_effect=fake_search if name == "search_products" else lambda: fake_search(""))
            patcher.start()
            self.addCleanup(patcher.stop)

    # helpers

    def open(self, path):
        self.browser.get(self.live_server_url + path)
        try:
            WebDriverWait(self.browser, self.WAIT).until(lambda b: b.execute_script("return !!window.htmx"))
        except TimeoutException:
            self.skipTest("htmx could not load from the CDN (no internet?)")
        self.browser.execute_script("window.noReload = true")   # disappears if the whole page reloads

    def wait_until(self, check, message):
        WebDriverWait(self.browser, self.WAIT).until(lambda b: check(), message)

    def page_did_not_reload(self):
        return self.browser.execute_script("return window.noReload === true")

    def toast_text(self):
        return self.browser.execute_script("return (document.getElementById('toast-message') || {}).textContent || ''")

    def log_in(self):
        user = get_user_model().objects.create_user(username="selenium", password="test-pass-123")
        self.client.force_login(user)                       # makes a session; give its cookie to Chrome
        self.browser.get(self.live_server_url + "/static/main/main.css")   # any page on the site, so Chrome accepts the cookie
        self.browser.add_cookie({"name": "sessionid", "value": self.client.cookies["sessionid"].value, "path": "/"})
        return user

    def click(self, element):
        # the site scrolls smoothly, so jump straight to the element first or the click lands mid-scroll
        self.browser.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'})", element)
        element.click()

    def results_text(self):
        return self.browser.find_element(By.ID, "discover-results").text

    # tests

    def test_live_search_updates_results_without_reloading(self):
        self.open("/")
        self.browser.find_element(By.NAME, "q").send_keys("susu")
        self.wait_until(lambda: 'results for "susu"' in self.results_text(), "live search never showed the results")
        self.assertTrue(self.page_did_not_reload())         # HTMX swapped only the results
        self.assertIn("q=susu", self.browser.current_url)  # hx-push-url kept the address in sync

    def test_grade_chip_can_be_picked_while_products_are_shown(self):
        # the bug from 30 Oct: hidden "grade" inputs in the compare buttons crashed the chip script.
        # Logged-in users get those compare forms, so log in to really cover it
        self.log_in()
        self.open("/?q=susu")
        self.click(self.browser.find_element(By.ID, "filter-open"))
        chip = self.browser.find_element(By.CSS_SELECTOR, "#filter-dialog input[name='grade'][value='E']").find_element(By.XPATH, "..")
        self.click(chip)
        self.wait_until(lambda: "is-selected" in chip.get_attribute("class"), "the E chip never turned on")

    def test_filters_apply_without_reloading(self):
        self.open("/?q=susu")
        self.click(self.browser.find_element(By.ID, "filter-open"))
        self.click(self.browser.find_element(By.CSS_SELECTOR, "#filter-dialog input[name='grade'][value='A']").find_element(By.XPATH, ".."))
        self.click(self.browser.find_element(By.CSS_SELECTOR, "#filter-dialog button[type='submit']"))
        self.wait_until(lambda: "grade=A" in self.browser.current_url, "the address never got grade=A")
        self.wait_until(lambda: "Filters (1)" in self.browser.find_element(By.ID, "filter-open").text, "Filters button didn't update")
        self.assertFalse(self.browser.execute_script("return document.getElementById('filter-dialog').open"))   # dialog closed
        self.assertTrue(self.page_did_not_reload())

    def test_heart_saves_instantly_and_shows_the_toast(self):
        user = self.log_in()
        self.open("/?q=susu")
        heart = self.browser.find_element(By.CSS_SELECTOR, ".discover-fav")
        self.click(heart)
        self.assertEqual(heart.get_attribute("aria-pressed"), "true")   # optimistic: red right away
        self.wait_until(lambda: "added to your saved products" in self.toast_text(), "the Saved toast never showed")
        self.assertEqual(FavoriteProduct.objects.filter(user=user).count(), 1)   # and it really is in the database

    def test_offline_search_keeps_results_and_shows_try_again(self):
        self.open("/?q=susu")
        cards_before = len(self.browser.find_elements(By.CSS_SELECTOR, ".discover-card"))
        self.browser.execute_cdp_cmd("Network.enable", {})
        self.browser.execute_cdp_cmd("Network.emulateNetworkConditions",
                                     {"offline": True, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        try:
            box = self.browser.find_element(By.NAME, "q")
            box.send_keys(" milk")
            self.wait_until(lambda: "couldn't reach SpoonFeed" in self.toast_text(), "no 'No connection' toast")
            self.assertTrue(self.browser.find_elements(By.ID, "discover-retry"))          # the Try again box
            self.assertEqual(len(self.browser.find_elements(By.CSS_SELECTOR, ".discover-card")), cards_before)   # old results stay
        finally:
            self.browser.execute_cdp_cmd("Network.emulateNetworkConditions",
                                         {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
