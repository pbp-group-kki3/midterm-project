from django.contrib.auth.models import User
from django.test import TestCase

PLACEHOLDER_PATHS = [
    '/modules/',
    '/styleguide/',
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

    def test_logo_is_an_svg(self):
        response = self.client.get('/modules/')
        self.assertContains(response, '<svg class="logo"')

    def test_logged_in_navbar_shows_avatar_with_first_letter(self):
        user = User.objects.create_user(username='reyhan', password='testpass123')
        self.client.force_login(user)
        response = self.client.get('/modules/')
        self.assertContains(response, 'class="user-chip"')
        self.assertContains(response, 'class="avatar avatar-sm"')
        self.assertRegex(response.content.decode(), r'class="avatar avatar-sm">\s*R\s*</span>')
