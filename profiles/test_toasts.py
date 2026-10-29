from collections import Counter
from html.parser import HTMLParser
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.messages import DEFAULT_LEVELS, WARNING
from django.contrib.messages.storage.base import Message
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.html import escape


class ToastTests(TestCase):
    # Every module must use one renderer and the same notification controller.
    def test_messages_render_once_across_modules(self):
        class ToastIDs(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = Counter()

            def handle_starttag(self, tag, attrs):
                element_id = dict(attrs).get('id')
                if element_id:
                    self.ids[element_id] += 1

        owner = User.objects.create_user('toast-owner')
        templates = [
            'profiles/login.html', 'profiles/register.html', 'profiles/profile.html',
            'comparison/compare.html', 'main/main.html', 'main/product_detail.html',
            'meal_plan/plan_list.html',
        ]
        for template in templates:
            with self.subTest(template=template):
                request = RequestFactory().get('/')
                request.user = owner if template == 'profiles/profile.html' else AnonymousUser()
                request.session = {}
                marker = 'Shared notification example'
                html = render_to_string(template, {
                    'user': request.user,
                    'profile': owner.profile,
                    'messages': [Message(WARNING, marker)],
                    'DEFAULT_MESSAGE_LEVELS': DEFAULT_LEVELS,
                    'products': [],
                    'product': None,
                    'show_compare_panel': False,
                }, request=request)
                parser = ToastIDs()
                parser.feed(html)
                for element_id in ['toast-component', 'toast-messages', 'toast-close', 'toast-title', 'toast-message', 'toast-symbol']:
                    self.assertEqual(parser.ids[element_id], 1, element_id)
                self.assertEqual(html.count(marker), 1)
                self.assertEqual(html.count('/static/js/toast.js'), 1)
                self.assertNotIn('toast-container', parser.ids)
                self.assertNotIn('/comparison/js/toast.js', html)

    # Comparison warnings must not also appear as a separate inline alert.
    def test_unavailable_comparison_warning_is_rendered_once(self):
        session = self.client.session
        session['compare'] = ['111', '222']
        session.save()
        with patch('comparison.views.load_comparison_products', return_value=([], ['111', '222'])):
            response = self.client.get(reverse('comparison:compare_products'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Some selected products could not be loaded.', count=1)
        self.assertContains(response, 'id="toast-component"', count=1)
        self.assertEqual(self.client.session['compare'], ['111', '222'])

    # Messages are escaped as data rather than inserted as executable HTML.
    def test_message_content_is_escaped(self):
        payload = '<script>alert("message")</script>'
        html = render_to_string('components/toasts.html', {
            'messages': [Message(WARNING, payload)],
            'DEFAULT_MESSAGE_LEVELS': DEFAULT_LEVELS,
        })
        self.assertNotIn(payload, html)
        self.assertIn(escape(payload), html)
        self.assertIn('aria-label="Dismiss notification"', html)

    # The shared controller replaces the obsolete module-specific asset.
    def test_shared_controller_resolves_without_legacy_asset(self):
        self.assertIsNotNone(finders.find('js/toast.js'))
        self.assertIsNone(finders.find('comparison/js/toast.js'))
