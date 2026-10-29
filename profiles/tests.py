from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from profiles.models import Profile
from profiles.services import get_preferences
from profiles.forms import AccountForm
from comparison.models import SavedComparison
from main.models import FavoriteProduct
from meal_plan.models import MealPlan
from unittest.mock import patch
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit
from django.contrib import messages

class ProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword123')

    def test_profile_auto_created(self):
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertIsInstance(self.user.profile, Profile)
        self.assertEqual(self.user.profile.diet, [])
        self.assertEqual(self.user.profile.allergies, [])

    def test_profile_string_representation(self):
        self.assertEqual(str(self.user.profile), "testuser's Profile")


class ProfileServicesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='serviceuser', password='testpassword123')
        self.profile = self.user.profile

    def test_get_preferences_unauthenticated(self):
        anon_user = AnonymousUser()
        prefs = get_preferences(anon_user)
        self.assertEqual(prefs['diet'], [])
        self.assertEqual(prefs['off_tags'], [])

    def test_get_preferences_authenticated_default(self):
        prefs = get_preferences(self.user)
        self.assertEqual(prefs['diet'], [])
        self.assertEqual(prefs['exclude_ingredients'], '')
        self.assertEqual(prefs['off_tags'], [])

    def test_get_preferences_with_halal_and_allergies(self):
        self.profile.diet = 'halal'
        self.profile.allergies = ['Milk', 'Peanuts', 'UnknownAllergy']
        self.profile.save()

        prefs = get_preferences(self.user)
        self.assertEqual(prefs['diet'], ['halal'])
        self.assertEqual(prefs['exclude_ingredients'], 'pork,bacon,ham,wine,beer')
        
        # 'UnknownAllergy' should be ignored by the map
        self.assertIn('en:milk', prefs['off_tags'])
        self.assertIn('en:peanuts', prefs['off_tags'])
        self.assertEqual(len(prefs['off_tags']), 2)
        
        self.assertIn('dairy', prefs['spoonacular_intolerances'])
        self.assertIn('peanut', prefs['spoonacular_intolerances'])


class ProfileViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='viewuser', password='testpassword123')
        self.profile = self.user.profile

    def test_register_view_get(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profiles/register.html')

    def test_profile_view_unauthenticated(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))

    def test_profile_view_authenticated(self):
        self.client.login(username='viewuser', password='testpassword123')
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profiles/profile.html')

    def test_profile_edit_post(self):
        self.client.login(username='viewuser', password='testpassword123')
        response = self.client.post(reverse('profile_edit'), {
            'action': 'update_preferences',
            'diet': ['vegan'],
            'allergies': ['Soy', 'Gluten'],
            'calorie_target': '2000',
            'meals_per_day': '4'
        })
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.diet, ['vegan'])
        self.assertEqual(self.profile.allergies, ['Soy', 'Gluten'])
        self.assertEqual(self.profile.calorie_target, 2000)
        self.assertEqual(self.profile.meals_per_day, 3)
        self.assertRedirects(response, reverse('profile') + '?section=preferences')

    def test_profile_picture_delete(self):
        self.client.login(username='viewuser', password='testpassword123')
        
        dummy_image = SimpleUploadedFile(name='test_image.jpg', content=b'', content_type='image/jpeg')
        self.profile.profile_picture = dummy_image
        self.profile.save()
        self.assertTrue(bool(self.profile.profile_picture))

        response = self.client.post(reverse('profile_picture_delete'))
        self.profile.refresh_from_db()
        self.assertFalse(bool(self.profile.profile_picture))
        self.assertRedirects(response, reverse('profile'))

    def test_profile_delete(self):
        self.client.login(username='viewuser', password='testpassword123')
        self.assertTrue(User.objects.filter(username='viewuser').exists())
        
        response = self.client.post(reverse('profile_delete'))
        self.assertFalse(User.objects.filter(username='viewuser').exists())
        self.assertRedirects(response, '/')


# Check the integration gaps without using external product or recipe APIs.
class ProfileIntegrationTests(TestCase):
    def setUp(self):
        self.password = 'SpoonFeed-Test-Password-928!'
        self.user = User.objects.create_user('owner', 'owner@example.com', self.password)
        self.other = User.objects.create_user('other', password=self.password)
        self.client.force_login(self.user)

    def test_signup_has_unique_controls_and_displays_general_errors(self):
        response = Client().get(reverse('register'))
        self.assertContains(response, 'name="diet"', count=4)
        self.assertContains(response, 'name="allergies"', count=9)
        with patch('profiles.forms.SignupForm.clean', side_effect=ValidationError('Please retry signup.')):
            response = Client().post(reverse('register'), {
                'username': 'newuser', 'email': 'new@example.com',
                'password': self.password, 'confirm_password': self.password,
            })
        self.assertContains(response, 'Please retry signup.')

    # Duplicate emails keep field-specific feedback without a persistent banner.
    def test_signup_duplicate_email_uses_inline_error_only(self):
        client = Client()
        data = {
            'username': 'newuser', 'email': self.user.email,
            'password': self.password, 'confirm_password': self.password,
        }
        response = client.post(reverse('register'), data)
        self.assertContains(response, 'This email is already registered.', count=1)
        self.assertNotContains(response, 'Please fix the errors below to continue.')
        self.assertTrue(response.context['signup_form'].has_error('email'))
        self.assertFalse(User.objects.filter(username='newuser').exists())
        data['email'] = 'available@example.com'
        response = client.post(reverse('register'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.get(username='newuser').email, data['email'])

    # Step 1 uses the same signup validators but never saves an account.
    def test_signup_step1_validation_does_not_create_or_authenticate(self):
        client = Client()
        before = User.objects.count()
        response = client.post(reverse('register'), {
            'validate_step': '1', 'username': 'newuser', 'email': 'available@example.com',
            'password': self.password, 'confirm_password': self.password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True, 'errors': {}})
        self.assertEqual(User.objects.count(), before)
        self.assertNotIn('_auth_user_id', client.session)

    def test_signup_step1_rejects_registered_email_case_insensitively(self):
        response = Client().post(reverse('register'), {
            'validate_step': '1', 'username': 'newuser', 'email': self.user.email.upper(),
            'password': self.password, 'confirm_password': self.password,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])
        self.assertEqual(response.json()['errors']['email'][0]['message'], 'This email is already registered.')
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_signup_step1_preserves_username_and_password_validation(self):
        response = Client().post(reverse('register'), {
            'validate_step': '1', 'username': self.user.username, 'email': 'available@example.com',
            'password': self.password, 'confirm_password': 'different-password',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.json()['errors'])
        self.assertIn('password2', response.json()['errors'])

    def test_signup_step1_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        data = {
            'validate_step': '1', 'username': 'newuser', 'email': 'available@example.com',
            'password': self.password, 'confirm_password': self.password,
        }
        self.assertEqual(client.post(reverse('register'), data).status_code, 403)
        client.get(reverse('register'))
        response = client.post(reverse('register'), data, HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_final_signup_rechecks_email_after_step1(self):
        client = Client()
        data = {'username': 'newuser', 'email': 'available@example.com', 'password': self.password, 'confirm_password': self.password}
        preview = client.post(reverse('register'), {**data, 'validate_step': '1'})
        self.assertTrue(preview.json()['ok'])
        User.objects.create_user('taken-after-check', email=data['email'], password=self.password)
        response = client.post(reverse('register'), data)
        self.assertContains(response, 'This email is already registered.')
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_signup_and_preferences_preserve_multiple_selections(self):
        response = Client().post(reverse('register'), {
            'username': 'newuser', 'email': 'new@example.com',
            'password': self.password, 'confirm_password': self.password,
            'diet': ['halal', 'vegetarian'], 'allergies': ['Milk', 'Sesame'],
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.get(username='newuser').profile.diet, ['halal', 'vegetarian'])
        response = self.client.post(reverse('profile_edit'), {
            'action': 'update_preferences', 'diet': ['halal', 'vegetarian'],
            'allergies': ['Milk', 'Peanuts'], 'calorie_target': '2000',
        })
        self.assertEqual(response.status_code, 302)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.diet, ['halal', 'vegetarian'])
        self.assertEqual(self.user.profile.allergies, ['Milk', 'Peanuts'])
        response = self.client.post(reverse('profile_edit'), {
            'action': 'update_preferences', 'diet': ['vegan'], 'allergies': ['invalid'],
        })
        self.assertEqual(response.status_code, 400)
        selected_diets = [checkbox.data['value'] for checkbox in response.context['preferences_form']['diet'] if checkbox.data['selected']]
        self.assertEqual(selected_diets, ['vegan'])
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.diet, ['halal', 'vegetarian'])
        self.client.post(reverse('profile_edit'), {'action': 'update_preferences'})
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.diet, [])
        self.assertEqual(self.user.profile.allergies, [])

    def test_account_errors_keep_edit_controls_visible(self):
        response = self.client.post(reverse('profile_edit'), {
            'action': 'update_account', 'full_name': 'Draft name', 'date_of_birth': 'invalid',
        })
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'id="profile-account-form" data-editing="true"', status_code=400)
        self.assertContains(response, 'id="edit-profile-btn" class="btn btn-secondary" hidden', status_code=400)
        self.assertContains(response, 'value="Draft name"', status_code=400)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, '')

    def test_birth_date_validation_and_legacy_values(self):
        for value in ['invalid', (timezone.localdate() + timedelta(days=1)).isoformat()]:
            with self.subTest(value=value):
                form = AccountForm({'date_of_birth': value}, instance=self.user.profile, editable=True)
                self.assertFalse(form.is_valid())
                self.assertIn('date_of_birth', form.errors)
                self.user.profile.refresh_from_db()
        self.user.profile.date_of_birth = '17/05/2000'
        self.user.profile.save()
        self.assertIn('value="2000-05-17"', str(AccountForm(instance=self.user.profile)['date_of_birth']))
        self.user.profile.date_of_birth = 'legacy text'
        self.user.profile.save()
        form = AccountForm({'date_of_birth': ''}, instance=self.user.profile, editable=True)
        self.assertFalse(form.is_valid())
        self.user.profile.refresh_from_db()
        form = AccountForm({'date_of_birth': '', 'clear_birth_date': 'on'}, instance=self.user.profile, editable=True)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.date_of_birth, '')

    def test_profile_forms_are_separate_and_protected(self):
        class FormParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.open_form = None
                self.forms = []
                self.nested = False

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'form':
                    self.nested = self.nested or self.open_form is not None
                    self.open_form = {'action': attrs.get('action'), 'csrf': False}
                    self.forms.append(self.open_form)
                elif tag == 'input' and attrs.get('name') == 'csrfmiddlewaretoken' and self.open_form is not None:
                    self.open_form['csrf'] = True

            def handle_endtag(self, tag):
                if tag == 'form':
                    self.open_form = None

        response = self.client.get(reverse('profile'))
        parser = FormParser()
        parser.feed(response.content.decode())
        self.assertFalse(parser.nested)
        for action in ['logout', 'profile_edit', 'profile_picture_delete', 'profile_delete']:
            form = next(form for form in parser.forms if form['action'] == reverse(action))
            self.assertTrue(form['csrf'], action)

    def test_saved_categories_render_real_owned_records(self):
        FavoriteProduct.objects.create(user=self.user, barcode='111', product_name='Owned product')
        FavoriteProduct.objects.create(user=self.other, barcode='222', product_name='Private product')
        SavedComparison.objects.create(user=self.user, name='Owned comparison', barcodes=['111', '222'])
        for category in ['all', 'product', 'comparison', 'article', 'meal']:
            response = self.client.get(reverse('profile_saved'), {'category': category})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['active_section'], 'saved')
            self.assertNotContains(response, 'Private product')
        response = self.client.get(reverse('profile_saved'), {'category': 'comparison'})
        self.assertContains(response, 'Owned comparison')
        self.assertNotContains(response, 'Owned product')

    def test_saved_has_no_meal_plans_category(self):
        MealPlan.objects.create(
            user=self.user, name='Green week', date=timezone.localdate(),
            timeframe='week', days=7, calorie_goal=2000,
        )
        response = self.client.get(reverse('profile_saved'), {'category': 'all'})
        self.assertNotContains(response, 'category=meal-plan')
        self.assertNotContains(response, 'Green week')
        response = self.client.get(reverse('profile_saved'), {'category': 'meal-plan'})
        self.assertEqual(response.status_code, 404)

    def test_saved_comparison_opens_without_changing_selection(self):
        saved = SavedComparison.objects.create(user=self.user, name='Saved lineup', barcodes=['111', '222'])
        session = self.client.session
        session['compare'] = ['333']
        session.save()
        products = [{'compare_barcode': code, 'product_name': 'Example', 'nutriments': {}} for code in saved.barcodes]
        with patch('comparison.views.load_comparison_products', return_value=(products, [])):
            response = self.client.get(reverse('profile_saved_comparison', args=[saved.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['viewing_saved'])
        self.assertNotContains(response, 'compare-remove-trigger')
        self.assertEqual(self.client.session['compare'], ['333'])
        self.assertContains(response, reverse('profile_saved') + '?category=comparison')

    # Reading a saved lineup must not consume an unfinished active comparison form.
    def test_saved_comparison_preserves_pending_save_state(self):
        saved = SavedComparison.objects.create(user=self.user, name='Saved lineup', barcodes=['111', '222'])
        pending = {'data': {'name': 'Draft'}, 'non_field_errors': ['Please retry.']}
        session = self.client.session
        session['compare'] = ['333']
        session['compare_has_removed'] = True
        session['comparison_save_errors'] = pending
        session.save()
        products = [{'compare_barcode': code, 'product_name': 'Example', 'nutriments': {}} for code in saved.barcodes]
        with patch('comparison.views.load_comparison_products', return_value=(products, [])):
            response = self.client.get(reverse('profile_saved_comparison', args=[saved.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session['compare'], ['333'])
        self.assertTrue(self.client.session['compare_has_removed'])
        self.assertEqual(self.client.session['comparison_save_errors'], pending)
        self.assertFalse(response.context['show_add_product'])
        self.assertFalse(response.context['can_save'])
        self.assertFalse(response.context['open_save_dialog'])
        self.assertNotContains(response, 'compare-remove-trigger')

    def test_saved_removal_enforces_ownership_and_removes_only_bookmark(self):
        own = FavoriteProduct.objects.create(user=self.user, barcode='111')
        private = FavoriteProduct.objects.create(user=self.other, barcode='222')
        private_comparison = SavedComparison.objects.create(user=self.other, name='Private', barcodes=['111', '222'])
        self.assertEqual(self.client.get(reverse('profile_saved_comparison', args=[private_comparison.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('profile_saved_remove', args=['product', private.pk])).status_code, 404)
        session = self.client.session
        session['compare'] = ['111']
        session.save()
        self.client.post(reverse('profile_saved_remove', args=['product', own.pk]))
        self.assertFalse(FavoriteProduct.objects.filter(pk=own.pk).exists())
        self.assertTrue(FavoriteProduct.objects.filter(pk=private.pk).exists())
        self.assertEqual(self.client.session['compare'], ['111'])

    def test_login_default_safe_next_unsafe_next_and_authenticated_access(self):
        target = reverse('profile_saved') + '?category=comparison'
        destinations = [
            ('', reverse('main:show_main')), (target, target),
            (reverse('comparison:compare_products'), reverse('comparison:compare_products')),
            ('https://example.org/', reverse('main:show_main')), (reverse('login'), reverse('main:show_main')),
        ]
        for destination, expected in destinations:
            with self.subTest(destination=destination):
                response = Client().post(reverse('login'), {'username': self.user.username, 'password': self.password, 'next': destination})
                self.assertEqual(response.url, expected)
        self.assertEqual(self.client.get(reverse('login')).url, reverse('main:show_main'))
        response = Client().get(reverse('profile_saved'), {'category': 'comparison'})
        login = Client().get(response.url)
        self.assertEqual(login.context['next'], target)
        self.assertContains(login, 'name="next"')

    def test_destructive_actions_reject_get_and_missing_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for action in ['logout', 'profile_delete', 'profile_picture_delete']:
            url = reverse(action)
            self.assertEqual(self.client.get(url).status_code, 405)
            self.assertEqual(client.post(url).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_multiple_diets_require_explicit_plan_choice(self):
        self.user.profile.diet = ['halal', 'vegetarian']
        self.user.profile.save()
        response = self.client.get(reverse('meal_plan:plan_create'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form']['diet'].value(), '')
        response = self.client.post(reverse('meal_plan:plan_create'), {'diet': ''})
        self.assertIn('diet', response.context['form'].errors)

    # Signup redirects to Login without creating an authenticated session.
    def test_signup_login_flow_preserves_only_safe_next(self):
        targets = [
            ('', ''), ('/meal-plan/plans/7/?day=2', '/meal-plan/plans/7/?day=2'),
            (reverse('profile_saved') + '?category=comparison', reverse('profile_saved') + '?category=comparison'),
            ('https://example.org/private/', ''), (reverse('login'), ''),
        ]
        for index, (target, expected) in enumerate(targets):
            with self.subTest(target=target):
                client = Client()
                response = client.post(reverse('register'), {
                    'username': f'signup{index}', 'email': f'signup{index}@example.com',
                    'password': self.password, 'confirm_password': self.password, 'next': target,
                })
                self.assertEqual(response.status_code, 302)
                self.assertEqual(urlsplit(response.url).path, reverse('login'))
                self.assertEqual(parse_qs(urlsplit(response.url).query).get('next', [''])[0], expected)
                self.assertNotIn('_auth_user_id', client.session)
                login = client.get(response.url)
                self.assertEqual(login.context['next'], expected)
                self.assertContains(login, 'Your account has been created. Please log in.', count=1)
                self.assertContains(login, 'id="toast-component"', count=1)

    def test_meal_plan_login_and_authenticated_next(self):
        target = '/meal-plan/plans/7/?day=2'
        response = Client().post(reverse('login'), {
            'username': self.user.username, 'password': self.password, 'next': target,
        })
        self.assertEqual(response.url, target)
        self.assertEqual(self.client.get(reverse('login'), {'next': target}).url, target)
        self.assertEqual(self.client.get(reverse('login'), {'next': '//example.org/'}).url, reverse('main:show_main'))

    # The two sections render their own Edit controls and keep invalid drafts editable.
    def test_section_edit_states_and_cancel_restore_saved_values(self):
        self.user.profile.full_name = 'Saved name'
        self.user.profile.diet = ['halal']
        self.user.profile.save()
        idle = self.client.get(reverse('profile'))
        html = idle.content.decode()
        self.assertGreater(html.index('id="edit-profile-btn"'), html.index('id="sec-account"'))
        self.assertGreater(html.index('id="edit-preferences-btn"'), html.index('id="sec-preferences"'))
        self.assertContains(idle, 'id="preferences-fields" class="space-y-6" disabled')
        invalid = self.client.post(reverse('profile_edit'), {
            'action': 'update_preferences', 'diet': ['vegan'], 'calorie_target': '-1',
        })
        self.assertEqual(invalid.status_code, 400)
        self.assertTrue(invalid.context['preferences_editing'])
        self.assertNotContains(invalid, 'id="preferences-fields" class="space-y-6" disabled', status_code=400)
        self.assertContains(invalid, 'id="edit-preferences-btn" class="btn btn-secondary" hidden', status_code=400)
        restored = self.client.get(reverse('profile'), {'section': 'preferences'})
        self.assertEqual(restored.context['preferences_form']['diet'].value(), ['halal'])
        self.assertFalse(restored.context['preferences_editing'])
        self.client.post(reverse('profile_edit'), {
            'action': 'update_account', 'full_name': 'Draft name', 'date_of_birth': 'invalid',
        })
        restored = self.client.get(reverse('profile'))
        self.assertEqual(restored.context['account_form']['full_name'].value(), 'Saved name')
        self.assertFalse(restored.context['account_editing'])

    def test_profile_update_still_requires_authentication_and_uses_current_user(self):
        response = Client().post(reverse('profile_edit'), {'action': 'update_account', 'full_name': 'Unauthorized'})
        self.assertEqual(response.status_code, 302)
        self.client.post(reverse('profile_edit'), {
            'action': 'update_account', 'full_name': 'Owner name', 'user': self.other.pk,
        })
        self.user.profile.refresh_from_db()
        self.other.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, 'Owner name')
        self.assertEqual(self.other.profile.full_name, '')

    # Every base page renders one shared toast and no module-specific message copy.
    def test_shared_toasts_render_messages_once_on_each_module(self):
        from django.contrib.messages.storage.cookie import CookieStorage
        from django.http import HttpResponse
        from django.test import RequestFactory

        for destination in [reverse('profile'), reverse('login'), reverse('register'), reverse('meal_plan:plan_list')]:
            with self.subTest(destination=destination):
                client = Client() if destination in [reverse('login'), reverse('register')] else self.client
                storage = CookieStorage(RequestFactory().get(destination))
                storage.add(messages.WARNING, 'Shared warning example')
                message_response = HttpResponse()
                storage.update(message_response)
                client.cookies.update(message_response.cookies)
                response = client.get(destination)
                self.assertContains(response, 'id="toast-component"', count=1)
                self.assertContains(response, '/static/js/toast.js', count=1)
                self.assertContains(response, 'Shared warning example', count=1)
                self.assertNotContains(response, 'id="toast-container"')
                self.assertNotContains(response, 'mealplan-alerts')

    def test_comparison_keeps_ajax_toast_api_and_has_no_duplicate_warning(self):
        session = self.client.session
        session['compare'] = ['111', '222']
        session.save()
        with patch('comparison.views.load_comparison_products', return_value=([], ['111', '222'])):
            response = self.client.get(reverse('comparison:compare_products'))
        self.assertContains(response, 'Some selected products could not be loaded.', count=1)
        self.assertContains(response, 'id="toast-component"', count=1)
        self.assertNotContains(response, '/comparison/js/toast.js')
