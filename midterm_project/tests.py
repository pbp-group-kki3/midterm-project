from django.test import TestCase

PLACEHOLDER_PATHS = [
    '/modules/',
    '/meal-plan/',
    '/compare/',
    '/food-of-the-day/',
    '/blog/',
    '/profiles/',
    '/profiles/login/',
    '/profiles/register/',
]

NAV_PATHS = ['/', '/meal-plan/', '/blog/', '/profiles/login/', '/profiles/register/']


class SharedLayoutTests(TestCase):
    def test_every_page_renders_without_server_error(self):
        for path in PLACEHOLDER_PATHS:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertLess(response.status_code, 500)

    def test_navbar_links_are_present(self):
        response = self.client.get('/modules/')
        for path in NAV_PATHS:
            with self.subTest(path=path):
                self.assertContains(response, 'href="%s"' % path)
