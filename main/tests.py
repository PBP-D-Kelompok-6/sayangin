from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from main.models import UserProfile, InstitutionProfile


class LandingAndMenuViewTests(TestCase):
    def test_landing_page_renders_new_design(self):
        response = self.client.get(reverse('main:show_main'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')
        self.assertContains(response, 'hero__wordmark')
        self.assertContains(response, 'Setiap barang di lemarimu punya <em>jalan pulang</em>')
        self.assertContains(response, 'KEBUTUHAN')

    def test_mobile_menu_page_renders_new_design(self):
        response = self.client.get(reverse('main:show_menu'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'menu.html')
        self.assertContains(response, 'Menu utama')
        self.assertContains(response, 'Jadi lembaga mitra')


class RegisterViewTests(TestCase):
    def test_register_page_renders_new_design(self):
        response = self.client.get(reverse('main:show_register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'register.html')
        self.assertContains(response, 'onboard onboard--split')
        self.assertContains(response, 'Saya mendaftar sebagai')
        self.assertNotContains(response, 'Keranjangmu')

    def test_register_page_preselects_lembaga_when_queried(self):
        response = self.client.get(reverse('main:show_register') + '?tipe=lembaga')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_lembaga'])

    def test_register_personal_user_creates_account_logs_in_and_redirects(self):
        response = self.client.post(reverse('main:show_register'), {
            'jenis': 'pribadi',
            'email': 'nadia.rahma@email.com',
            'password': 'password123',
        })
        self.assertRedirects(response, reverse('main:edit_profile'))
        user = User.objects.get(email='nadia.rahma@email.com')
        self.assertEqual(user.username, 'nadia.rahma')
        self.assertEqual(user.profile.role, 'PERSONAL') # type: ignore
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_register_lembaga_user_creates_account_logs_in_and_redirects(self):
        response = self.client.post(reverse('main:show_register'), {
            'jenis': 'lembaga',
            'email': 'panti.harapan@email.com',
            'password': 'password123',
        })
        self.assertRedirects(response, reverse('main:edit_institution_profile'))
        user = User.objects.get(email='panti.harapan@email.com')
        self.assertEqual(user.profile.role, 'LEMBAGA') # type: ignore
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_register_derives_unique_username_on_collision(self):
        User.objects.create_user(username='nadia', email='other@email.com', password='password123')
        response = self.client.post(reverse('main:show_register'), {
            'jenis': 'pribadi',
            'email': 'nadia@email.com',
            'password': 'password123',
        })
        self.assertRedirects(response, reverse('main:edit_profile'))
        user = User.objects.get(email='nadia@email.com')
        self.assertEqual(user.username, 'nadia1')

    def test_register_rejects_invalid_email_and_short_password(self):
        response = self.client.post(reverse('main:show_register'), {
            'jenis': 'pribadi',
            'email': 'bukan-email',
            'password': 'short',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['errors'])
        self.assertIn('password', response.context['errors'])
        self.assertContains(response, 'aria-invalid="true"')
        self.assertEqual(User.objects.count(), 0)

class LoginViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='nadia.r',
            email='nadia@email.com',
            password='password123',
        )

    def test_login_page_renders_new_design(self):
        response = self.client.get(reverse('main:show_login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')
        self.assertContains(response, 'onboard onboard--split')
        self.assertContains(response, 'Masuk ke <em>akun</em>')

    def test_login_with_email_succeeds(self):
        response = self.client.post(reverse('main:show_login'), {
            'identity': 'nadia@email.com',
            'password': 'password123',
        })
        self.assertRedirects(response, reverse('main:show_main'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_login_with_invalid_credentials_marks_invalid(self):
        response = self.client.post(reverse('main:show_login'), {
            'identity': 'nadia@email.com',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-invalid="true"')


class OnboardingAndProfileEditTests(TestCase):
    def test_edit_personal_profile_renders_and_saves_all_fields(self):
        user = User.objects.create_user(username='nadia', email='nadia@email.com', password='password123')
        self.client.login(username='nadia', password='password123')

        get_res = self.client.get(reverse('main:edit_profile'))
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, 'Kenalan <em>dulu</em>, yuk')
        self.assertContains(get_res, 'Label alamat')

        post_res = self.client.post(reverse('main:edit_profile'), {
            'full_name': 'Nadia Rahma',
            'phone_number': '081234564410',
            'address_label': 'KOS',
            'address': 'Jl. Margonda Raya No. 10',
            'city': 'Depok',
            'postal_code': '16424',
            'is_primary_address': 'on',
        })
        self.assertRedirects(post_res, reverse('main:show_profile'))

        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.full_name, 'Nadia Rahma')
        self.assertEqual(profile.phone_number, '081234564410')
        self.assertEqual(profile.address_label, 'KOS')
        self.assertEqual(profile.address, 'Jl. Margonda Raya No. 10')
        self.assertEqual(profile.city, 'Depok')
        self.assertEqual(profile.postal_code, '16424')
        self.assertTrue(profile.is_primary_address)

    def test_edit_institution_profile_renders_and_saves_all_fields(self):
        user = User.objects.create_user(username='panti', email='panti@email.com', password='password123')
        user.profile.role = 'LEMBAGA' # type: ignore
        user.profile.save() # type: ignore
        self.client.login(username='panti', password='password123')

        get_res = self.client.get(reverse('main:edit_institution_profile'))
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, 'Data <em>lembaga</em>')
        self.assertContains(get_res, 'Panti werdha')

        post_res = self.client.post(reverse('main:edit_institution_profile'), {
            'name': 'Panti Werdha Kasih',
            'institution_type': 'PANTI_WERDHA',
            'address': 'Jl. Melati No. 5, Bandung',
            'person_in_charge': 'Budi Santoso',
            'contact_phone': '081122334455',
        })
        self.assertRedirects(post_res, reverse('main:show_lembaga_profile'))

        inst = InstitutionProfile.objects.get(user=user)
        self.assertEqual(inst.name, 'Panti Werdha Kasih')
        self.assertEqual(inst.institution_type, 'PANTI_WERDHA')
        self.assertEqual(inst.address, 'Jl. Melati No. 5, Bandung')
        self.assertEqual(inst.person_in_charge, 'Budi Santoso')
        self.assertEqual(inst.contact_phone, '081122334455')


class ProfileAndLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='nadia.r',
            email='nadia@email.com',
            password='password123',
        )
        profile = self.user.profile # type: ignore
        profile.full_name = 'Nadia Rahma'
        profile.phone_number = '081234564410'
        profile.address_label = 'RUMAH'
        profile.address = 'Jl. Margonda Raya No. 10'
        profile.city = 'Depok'
        profile.postal_code = '16424'
        profile.is_primary_address = True
        profile.save()

    def test_profile_page_renders_a6_and_a7_design(self):
        self.client.login(username='nadia.r', password='password123')
        response = self.client.get(reverse('main:show_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profil.html')
        self.assertContains(response, 'Halo, <em>Nadia</em>')
        self.assertContains(response, 'profile__grid')
        self.assertContains(response, 'Rumah · utama')
        self.assertContains(response, 'Jl. Margonda Raya No. 10, Depok 16424')
        self.assertContains(response, 'Bantuan &amp; kebijakan')
        self.assertContains(response, 'site-header__actions')
        self.assertContains(response, 'cdn.tailwindcss.com')
        self.assertContains(response, 'id="keluar"')
        self.assertContains(response, 'Keluar dari <em>Sayangin</em>?')

    def test_logout_post_clears_session_and_redirects_to_landing(self):
        self.client.login(username='nadia.r', password='password123')
        response = self.client.post(reverse('main:logout_user'))
        self.assertRedirects(response, reverse('main:show_main'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_lembaga_pipeline_requires_data_lembaga_before_dashboard(self):
        lembaga_user = User.objects.create_user(
            username='panti.harapan',
            email='panti@email.com',
            password='password123',
        )
        lembaga_user.profile.role = 'LEMBAGA' # type: ignore
        lembaga_user.profile.save() # type: ignore

        # Logging in without InstitutionProfile redirects to Step 2 (edit_institution_profile)
        login_res = self.client.post(reverse('main:show_login'), {
            'identity': 'panti@email.com',
            'password': 'password123',
        })
        self.assertRedirects(login_res, reverse('main:edit_institution_profile'))

        # Direct access to show_lembaga_profile also redirects to edit_institution_profile
        dash_res = self.client.get(reverse('main:show_lembaga_profile'))
        self.assertRedirects(dash_res, reverse('main:edit_institution_profile'))

        # Completing Step 2 (Data lembaga) redirects to show_lembaga_profile and renders new design
        post_res = self.client.post(reverse('main:edit_institution_profile'), {
            'name': 'Panti Asuhan Harapan',
            'institution_type': 'PANTI_ASUHAN',
            'address': 'Jl. Kenanga No. 12, Depok',
            'person_in_charge': 'Siti Aminah',
            'contact_phone': '081298765432',
        })
        self.assertRedirects(post_res, reverse('main:show_lembaga_profile'))

        final_res = self.client.get(reverse('main:show_lembaga_profile'))
        self.assertEqual(final_res.status_code, 200)
        self.assertTemplateUsed(final_res, 'lembaga.html')
        self.assertContains(final_res, 'org-dash')
        self.assertContains(final_res, 'Halo, <em>Panti Asuhan Harapan</em>')
        self.assertContains(final_res, 'Siti Aminah')
        self.assertContains(final_res, 'Jl. Kenanga No. 12, Depok')
        self.assertContains(final_res, 'id="keluar"')


