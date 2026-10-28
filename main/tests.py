import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from main.models import UserProfile, InstitutionProfile, UserAddress


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
        self.assertContains(response, 'Halo, <em data-user-firstname>Nadia</em>')
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


class MultipleAddressesRajaOngkirAndAjaxTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='nadia.r',
            email='nadia@email.com',
            password='password123',
        )
        profile = self.user.profile # type: ignore
        profile.full_name = 'Nadia Rahma'
        profile.phone_number = '081234564410'
        profile.save()
        self.client.login(username='nadia.r', password='password123')

    def test_add_multiple_addresses_rumah_kos_apartemen_with_rajaongkir_ids(self):
        # 1. Add Rumah in Depok via AJAX
        res1 = self.client.post(reverse('main:api_add_address'), {
            'label': 'RUMAH',
            'recipient_name': 'Nadia Rahma',
            'phone_number': '081234564410',
            'address': 'Jl. Margonda Raya No. 10',
            'city': 'Depok',
            'postal_code': '16424',
            'is_primary': 'on',
        })
        self.assertEqual(res1.status_code, 201)
        data1 = res1.json()
        self.assertEqual(data1['status'], 'ok')
        self.assertEqual(data1['address']['rajaongkir_city_id'], '115')
        self.assertEqual(data1['address']['province'], 'Jawa Barat')
        self.assertTrue(data1['address']['is_primary'])

        # 2. Add Kos in Bandung (not primary)
        res2 = self.client.post(reverse('main:api_add_address'), {
            'label': 'KOS',
            'recipient_name': 'Nadia Rahma',
            'phone_number': '081234564410',
            'address': 'Jl. Cisitu Indah No. 4',
            'city': 'Bandung',
            'postal_code': '40135',
        })
        self.assertEqual(res2.status_code, 201)
        data2 = res2.json()
        self.assertEqual(data2['address']['rajaongkir_city_id'], '23')
        self.assertFalse(data2['address']['is_primary'])

        # 3. Add Apartemen in Jakarta Selatan as new primary
        res3 = self.client.post(reverse('main:api_add_address'), {
            'label': 'APARTEMEN',
            'recipient_name': 'Nadia Rahma',
            'phone_number': '081234564410',
            'address': 'Apartemen Kalibata City Tower Ebony Lt. 12',
            'city': 'Jakarta Selatan',
            'postal_code': '12750',
            'is_primary': 'on',
        })
        self.assertEqual(res3.status_code, 201)
        data3 = res3.json()
        self.assertEqual(data3['address']['label'], 'APARTEMEN')
        self.assertEqual(data3['address']['label_display'], 'Apartemen')
        self.assertEqual(data3['address']['rajaongkir_city_id'], '153')
        self.assertTrue(data3['address']['is_primary'])
        self.assertEqual(len(data3['addresses']), 3)

        # Verify UserProfile synced to the primary address (Apartemen in Jakarta Selatan)
        self.user.profile.refresh_from_db() # type: ignore
        self.assertEqual(self.user.profile.address_label, 'APARTEMEN') # type: ignore
        self.assertEqual(self.user.profile.city, 'Jakarta Selatan') # type: ignore

        # 4. Set Kos (Bandung) as primary via AJAX
        kos_id = data2['address']['id']
        res_primary = self.client.post(reverse('main:api_set_primary_address', args=[kos_id]))
        self.assertEqual(res_primary.status_code, 200)
        self.user.profile.refresh_from_db() # type: ignore
        self.assertEqual(self.user.profile.address_label, 'KOS') # type: ignore
        self.assertEqual(self.user.profile.city, 'Bandung') # type: ignore

        # 5. Delete Apartemen address via AJAX
        apt_id = data3['address']['id']
        res_del = self.client.post(reverse('main:api_delete_address', args=[apt_id]))
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(UserAddress.objects.filter(user=self.user).count(), 2)

    def test_django_serializers_json_endpoints_and_profile_ajax(self):
        UserAddress.objects.create(
            user=self.user,
            label='RUMAH',
            recipient_name='Nadia Rahma',
            phone_number='081234564410',
            address='Jl. Margonda Raya No. 10',
            city='Depok',
            postal_code='16424',
            is_primary=True,
        )

        # Test Django core serializers endpoints
        json_addr_res = self.client.get(reverse('main:show_addresses_json'))
        self.assertEqual(json_addr_res.status_code, 200)
        serialized_addrs = json.loads(json_addr_res.content)
        self.assertEqual(len(serialized_addrs), 1)
        self.assertEqual(serialized_addrs[0]['model'], 'main.useraddress')
        self.assertEqual(serialized_addrs[0]['fields']['rajaongkir_city_id'], '115')

        json_prof_res = self.client.get(reverse('main:show_profile_json'))
        self.assertEqual(json_prof_res.status_code, 200)
        serialized_prof = json.loads(json_prof_res.content)
        self.assertEqual(serialized_prof[0]['model'], 'main.userprofile')

        # Test AJAX profile update & preferences update
        upd_res = self.client.post(reverse('main:api_update_profile'), {
            'full_name': 'Nadia Rahmawati',
            'email': 'nadia.baru@email.com',
            'phone_number': '081299998888',
        })
        self.assertEqual(upd_res.status_code, 200)
        self.assertEqual(upd_res.json()['user']['full_name'], 'Nadia Rahmawati')

        pref_res = self.client.post(
            reverse('main:api_update_preferences'),
            data=json.dumps({
                'sizes': ['S', 'M'],
                'categories': ['Atasan', 'Buku'],
                'reminder': False,
                'email_newsletter': True,
            }),
            content_type='application/json',
        )
        self.assertEqual(pref_res.status_code, 200)
        pref_data = pref_res.json()['preferences']
        self.assertEqual(pref_data['sizes'], ['S', 'M'])
        self.assertEqual(pref_data['categories'], ['Atasan', 'Buku'])
        self.assertFalse(pref_data['reminder'])
        self.assertTrue(pref_data['email_newsletter'])

    def test_filter_addresses_by_label_and_search_query(self):
        UserAddress.objects.create(
            user=self.user,
            label='RUMAH',
            address='Jl. Margonda Raya No. 10',
            city='Depok',
            is_primary=True,
        )
        UserAddress.objects.create(
            user=self.user,
            label='KOS',
            address='Jl. Cisitu Indah No. 4',
            city='Bandung',
            is_primary=False,
        )
        UserAddress.objects.create(
            user=self.user,
            label='APARTEMEN',
            address='Apartemen Kalibata City',
            city='Jakarta Selatan',
            is_primary=False,
        )

        # 1. Filter by label RUMAH via show_addresses_json and api_profile_data
        res_rumah = self.client.get(reverse('main:show_addresses_json') + '?label=RUMAH')
        self.assertEqual(res_rumah.status_code, 200)
        data_rumah = json.loads(res_rumah.content)
        self.assertEqual(len(data_rumah), 1)
        self.assertEqual(data_rumah[0]['fields']['label'], 'RUMAH')

        api_res_rumah = self.client.get(reverse('main:api_profile_data') + '?label=RUMAH')
        self.assertEqual(api_res_rumah.status_code, 200)
        self.assertEqual(len(api_res_rumah.json()['addresses']), 1)
        self.assertEqual(api_res_rumah.json()['addresses'][0]['label'], 'RUMAH')

        # 2. Filter by label KOS
        api_res_kos = self.client.get(reverse('main:api_profile_data') + '?label=KOS')
        self.assertEqual(len(api_res_kos.json()['addresses']), 1)
        self.assertEqual(api_res_kos.json()['addresses'][0]['label'], 'KOS')

        # 3. Search query q=Bandung
        api_res_q = self.client.get(reverse('main:api_profile_data') + '?q=Bandung')
        self.assertEqual(len(api_res_q.json()['addresses']), 1)
        self.assertEqual(api_res_q.json()['addresses'][0]['city'], 'Bandung')

        # 4. Search query with no match
        api_res_empty = self.client.get(reverse('main:api_profile_data') + '?q=NonExistentPlace')
        self.assertEqual(len(api_res_empty.json()['addresses']), 0)

        # 5. Profile page HTML renders filter chips and addresses
        profile_page = self.client.get(reverse('main:show_profile') + '?label=KOS')
        self.assertEqual(profile_page.status_code, 200)
        self.assertContains(profile_page, 'data-address-filter="KOS"')
        self.assertContains(profile_page, 'Jl. Cisitu Indah No. 4')


class SecurityAndGoogleAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='nadia.r',
            email='nadia@email.com',
            password='password123',
        )
        profile = self.user.profile # type: ignore
        profile.full_name = 'Nadia Rahma'
        profile.save()

    def test_change_password_validates_and_keeps_session_active(self):
        self.client.login(username='nadia.r', password='password123')

        # Wrong current password fails
        bad_res = self.client.post(reverse('main:api_change_password'), {
            'old_password': 'wrongpassword',
            'new_password1': 'newsecurepass123',
            'new_password2': 'newsecurepass123',
        })
        self.assertEqual(bad_res.status_code, 400)
        self.assertEqual(bad_res.json()['status'], 'error')

        # Valid password change succeeds and keeps user logged in
        ok_res = self.client.post(reverse('main:api_change_password'), {
            'old_password': 'password123',
            'new_password1': 'newsecurepass123',
            'new_password2': 'newsecurepass123',
        })
        self.assertEqual(ok_res.status_code, 200)
        self.assertEqual(ok_res.json()['status'], 'ok')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newsecurepass123'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_google_login_and_register_personal_and_lembaga(self):
        # 1. Google OAuth page renders
        get_res = self.client.get(reverse('main:google_login') + '?mode=chooser')
        self.assertEqual(get_res.status_code, 200)
        self.assertTemplateUsed(get_res, 'google_oauth.html')
        state_personal = get_res.context['state']

        # 2. Register new PERSONAL user via Google callback
        cb_res = self.client.post(reverse('main:google_callback'), {
            'state': state_personal,
            'email': 'budi.google@gmail.com',
            'full_name': 'Budi Raharjo',
            'jenis': 'pribadi',
        })

        self.assertRedirects(cb_res, reverse('main:edit_profile'))
        budi = User.objects.get(email='budi.google@gmail.com')
        self.assertTrue(budi.profile.google_connected) # type: ignore
        self.assertEqual(budi.profile.google_email, 'budi.google@gmail.com') # type: ignore
        self.assertFalse(budi.has_usable_password())

        # Cannot disconnect Google before setting a password
        disc_fail = self.client.post(reverse('main:api_disconnect_google'))
        self.assertEqual(disc_fail.status_code, 400)

        # Set password without needing old_password (since created via Google)
        set_pw = self.client.post(reverse('main:api_change_password'), {
            'new_password1': 'budipassword123',
            'new_password2': 'budipassword123',
        })
        self.assertEqual(set_pw.status_code, 200)

        # Now disconnecting Google succeeds
        disc_ok = self.client.post(reverse('main:api_disconnect_google'))
        self.assertEqual(disc_ok.status_code, 200)
        budi.profile.refresh_from_db() # type: ignore
        self.assertFalse(budi.profile.google_connected) # type: ignore

        self.client.logout()

        # 3. Register new LEMBAGA user via Google callback -> routes to edit_institution_profile
        lembaga_init = self.client.get(reverse('main:google_login') + '?mode=chooser&jenis=lembaga')
        state_lembaga = lembaga_init.context['state']
        lembaga_cb = self.client.post(reverse('main:google_callback'), {
            'state': state_lembaga,
            'email': 'yayasan.cahaya@gmail.com',
            'full_name': 'Yayasan Cahaya',
            'jenis': 'lembaga',
        })
        self.assertRedirects(lembaga_cb, reverse('main:edit_institution_profile'))
        yayasan = User.objects.get(email='yayasan.cahaya@gmail.com')
        self.assertEqual(yayasan.profile.role, 'LEMBAGA') # type: ignore
        self.assertTrue(yayasan.profile.google_connected) # type: ignore

    def test_delete_account_validates_password_and_removes_user(self):
        self.client.login(username='nadia.r', password='password123')

        # Wrong password rejected
        bad_del = self.client.post(reverse('main:api_delete_account'), {
            'password': 'wrongpassword',
        })
        self.assertEqual(bad_del.status_code, 400)
        self.assertTrue(User.objects.filter(username='nadia.r').exists())

        # Correct password deletes user and logs out
        ok_del = self.client.post(reverse('main:api_delete_account'), {
            'password': 'password123',
        })
        self.assertEqual(ok_del.status_code, 200)
        self.assertEqual(ok_del.json()['redirect_url'], reverse('main:show_main'))
        self.assertFalse(User.objects.filter(username='nadia.r').exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_delete_account_requires_pass_when_empty_payload(self):
        self.client.login(username='nadia.r', password='password123')
        empty_res = self.client.post(reverse('main:api_delete_account'), data={},)

        self.assertEqual(empty_res.status_code, 400)
        self.assertIn("Masukkan kata sandi", empty_res.json()['message'])
        self.assertTrue(User.objects.filter(username='nadia.r').exists())

        bypass_res = self.client.post(reverse('main:api_delete_account'), data={'confirm_text': 'HAPUS'},)

        self.assertEqual(bypass_res.status_code, 400)
        self.assertTrue(User.objects.filter(username='nadia.r').exists())