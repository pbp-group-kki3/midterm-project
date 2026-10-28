from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from profiles.models import Profile
from profiles.services import get_preferences

class ProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword123')

    def test_profile_auto_created(self):
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertIsInstance(self.user.profile, Profile)
        self.assertEqual(self.user.profile.diet, 'none')
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
        self.assertEqual(prefs['diet'], 'none')
        self.assertEqual(prefs['off_tags'], [])

    def test_get_preferences_authenticated_default(self):
        prefs = get_preferences(self.user)
        self.assertEqual(prefs['diet'], 'none')
        self.assertEqual(prefs['exclude_ingredients'], '')
        self.assertEqual(prefs['off_tags'], [])

    def test_get_preferences_with_halal_and_allergies(self):
        self.profile.diet = 'halal'
        self.profile.allergies = ['Milk', 'Peanuts', 'UnknownAllergy']
        self.profile.save()

        prefs = get_preferences(self.user)
        self.assertEqual(prefs['diet'], 'halal')
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
            'diet': 'vegan',
            'allergies': 'Soy, Gluten',
            'calorie_target': '2000',
            'meals_per_day': '4'
        })
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.diet, 'vegan')
        self.assertEqual(self.profile.allergies, ['Soy', 'Gluten'])
        self.assertEqual(self.profile.calorie_target, 2000)
        self.assertEqual(self.profile.meals_per_day, 4)
        self.assertRedirects(response, reverse('profile'))

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