from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from donasi.models import Kebutuhan, Penawaran
from main.models import InstitutionProfile, UserAddress


class MainAuthAndRoleApiTests(APITestCase):
    def setUp(self):
        # enforce_csrf_checks=True memastikan API tetap bekerja tanpa CSRF token (seperti dari Flutter).
        self.client = APIClient(enforce_csrf_checks=True)
        self.personal = User.objects.create_user(
            username="nadia", email="nadia@email.com", password="password123"
        )
        self.personal.profile.full_name = "Nadia Rahma"  # type: ignore
        self.personal.profile.phone_number = "08123456789"  # type: ignore
        self.personal.profile.save()  # type: ignore

        self.lembaga = User.objects.create_user(
            username="panti_harapan", email="panti@email.com", password="password123"
        )
        self.lembaga.profile.role = "LEMBAGA"  # type: ignore
        self.lembaga.profile.save()  # type: ignore

    def test_register_login_me_and_logout_personal_and_lembaga(self):
        # 1. Tamu ditolak pada /api/auth/me/
        self.assertEqual(self.client.get(reverse("main:api_auth_me")).status_code, 403)

        # 2. Register akun personal baru (username otomatis dari email)
        reg_res = self.client.post(
            reverse("main:api_register"),
            {
                "email": "ira.baru@email.com",
                "password": "password123",
                "confirm": "password123",
                "role": "PERSONAL",
            },
            format="json",
        )
        self.assertEqual(reg_res.status_code, 201)
        reg_data = reg_res.json()
        self.assertEqual(reg_data["user"]["username"], "ira.baru")
        self.assertEqual(reg_data["user"]["role"], "PERSONAL")
        self.assertEqual(reg_data["next_step"], "edit_profile")

        # 3. /api/auth/me/ mengembalikan sesi user yang baru terdaftar
        me_res = self.client.get(reverse("main:api_auth_me"))
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["email"], "ira.baru@email.com")

        # 4. Logout menghapus sesi
        out_res = self.client.post(reverse("main:api_logout"))
        self.assertEqual(out_res.status_code, 200)
        self.assertEqual(self.client.get(reverse("main:api_auth_me")).status_code, 403)

        # 5. Register akun lembaga baru
        reg_l = self.client.post(
            reverse("main:api_register"),
            {"email": "yayasan@email.com", "password": "password123", "jenis": "lembaga"},
            format="json",
        )
        self.assertEqual(reg_l.status_code, 201)
        self.assertEqual(reg_l.json()["user"]["role"], "LEMBAGA")
        self.assertEqual(reg_l.json()["next_step"], "edit_institution_profile")
        self.client.post(reverse("main:api_logout"))

        # 6. Login menggunakan email & password salah ditolak
        bad_login = self.client.post(
            reverse("main:api_login"),
            {"identity": "nadia@email.com", "password": "wrong"},
            format="json",
        )
        self.assertEqual(bad_login.status_code, 400)
        self.assertEqual(bad_login.json()["status"], "error")

        ok_login = self.client.post(
            reverse("main:api_login"),
            {"identity": "nadia@email.com", "password": "password123"},
            format="json",
        )
        self.assertEqual(ok_login.status_code, 200)
        self.assertEqual(ok_login.json()["user"]["username"], "nadia")

    def test_role_permissions_enforce_personal_vs_lembaga(self):
        # Tamu ditolak di semua endpoint terlindungi
        guest = APIClient()
        self.assertEqual(guest.get(reverse("main:api_profile_data")).status_code, 403)
        self.assertEqual(guest.get(reverse("main:api_address-list")).status_code, 403)
        self.assertEqual(guest.get(reverse("main:api_lembaga_profile")).status_code, 403)

        # Personal ditolak di endpoint khusus Lembaga
        self.client.force_login(self.personal)
        self.assertEqual(self.client.get(reverse("main:api_lembaga_profile")).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("main:api_lembaga_profile"), {"name": "Fake"}, format="json").status_code,
            403,
        )

        # Lembaga ditolak di endpoint khusus Personal (alamat, update profil personal, preferensi)
        self.client.force_login(self.lembaga)
        self.assertEqual(self.client.get(reverse("main:api_address-list")).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("main:api_update_profile"), {"full_name": "X"}, format="json").status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse("main:api_update_preferences"), {"sizes": ["M"]}, format="json").status_code,
            403,
        )

    @override_settings(DEBUG=True)
    @patch.dict("os.environ", {"GOOGLE_CLIENT_ID": ""})
    def test_google_auth_dev_and_tokeninfo_and_connect(self):
        # Dev mode tanpa GOOGLE_CLIENT_ID
        r_dev = self.client.post(
            reverse("main:api_google_auth"),
            {"email": "google.user@gmail.com", "full_name": "Google User"},
            format="json",
        )
        self.assertEqual(r_dev.status_code, 201)
        self.assertTrue(r_dev.json()["is_new_user"])
        self.assertTrue(r_dev.json()["user"]["google_connected"])
        self.client.post(reverse("main:api_logout"))

        # Verifikasi id_token via Google tokeninfo (dimock)
        with patch("main.api.requests.get") as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "email": "nadia@email.com",
                    "name": "Nadia Google",
                    "email_verified": "true",
                    "aud": "client-123",
                },
            )
            with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "client-123"}):
                r_tok = self.client.post(
                    reverse("main:api_google_auth"),
                    {"id_token": "valid-jwt-token"},
                    format="json",
                )
        self.assertEqual(r_tok.status_code, 200)
        self.assertFalse(r_tok.json()["is_new_user"])
        self.assertEqual(r_tok.json()["user"]["username"], "nadia")

        # Saat DEBUG=False dan GOOGLE_CLIENT_ID kosong, id_token harus ditolak (bukan diterima tanpa cek aud).
        self.client.post(reverse("main:api_logout"))
        with override_settings(DEBUG=False), patch.dict("os.environ", {"GOOGLE_CLIENT_ID": ""}):
            r_unconf = self.client.post(
                reverse("main:api_google_auth"),
                {"id_token": "some-token"},
                format="json",
            )
            self.assertEqual(r_unconf.status_code, 503)
            self.assertEqual(r_unconf.json()["status"], "error")

    def test_pbp_django_auth_endpoints_login_logout_register(self):
        # Pakai Django Client standar dengan enforce_csrf_checks=True & form-encoded POST
        # persis seperti pbp_django_auth CookieRequest dari Flutter.
        flutter = Client(enforce_csrf_checks=True)

        # 1. Login gagal -> 401 dengan status: false
        bad = flutter.post(reverse("main:auth_login"), {"username": "nadia", "password": "wrong"})
        self.assertEqual(bad.status_code, 401)
        self.assertEqual(
            bad.json(),
            {"status": False, "message": "Email/username atau kata sandi salah."},
        )

        # 2. Login berhasil pakai username -> 200, session cookie terbentuk, role PERSONAL
        ok_user = flutter.post(reverse("main:auth_login"), {"username": "nadia", "password": "password123"})
        self.assertEqual(ok_user.status_code, 200)
        self.assertEqual(
            ok_user.json(),
            {
                "status": True,
                "message": "Login berhasil",
                "username": "nadia",
                "role": "PERSONAL",
            },
        )
        self.assertIn("sessionid", ok_user.cookies)
        self.assertEqual(flutter.get(reverse("main:api_auth_me")).status_code, 200)

        # 3. Logout tanpa CSRF token -> 200 & session terhapus
        out = flutter.post(reverse("main:auth_logout"))
        self.assertEqual(out.status_code, 200)
        self.assertEqual(out.json(), {"status": True, "message": "Logout berhasil"})
        self.assertEqual(flutter.get(reverse("main:api_auth_me")).status_code, 403)

        # 4. Login pakai email di field `username` untuk akun LEMBAGA -> role LEMBAGA
        ok_email = flutter.post(
            reverse("main:auth_login"),
            {"username": "panti@email.com", "password": "password123"},
        )
        self.assertEqual(ok_email.status_code, 200)
        self.assertEqual(
            ok_email.json(),
            {
                "status": True,
                "message": "Login berhasil",
                "username": "panti_harapan",
                "role": "LEMBAGA",
            },
        )
        flutter.post(reverse("main:auth_logout"))

        # 5. Register dari HP (/auth/register/)
        bad_reg = flutter.post(
            reverse("main:auth_register"),
            {"username": "baru", "email": "bukan-email", "password": "123"},
        )
        self.assertEqual(bad_reg.status_code, 400)
        self.assertIs(bad_reg.json()["status"], False)

        ok_reg = flutter.post(
            reverse("main:auth_register"),
            {"username": "renates", "email": "rena.hp@email.com", "password": "password123"},
        )
        self.assertEqual(ok_reg.status_code, 201)
        self.assertEqual(
            ok_reg.json(),
            {
                "status": True,
                "message": "Akun berhasil dibuat.",
                "username": "renates",
                "role": "PERSONAL",
            },
        )
        self.assertEqual(flutter.get(reverse("main:api_auth_me")).status_code, 200)


class MainAddressAndProfileViewSetTests(APITestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            username="nadia", email="nadia@email.com", password="password123"
        )
        self.user.profile.full_name = "Nadia Rahma"  # type: ignore
        self.user.profile.phone_number = "08123456789"  # type: ignore
        self.user.profile.save()  # type: ignore
        self.other = User.objects.create_user(
            username="ira", email="ira@email.com", password="password123"
        )
        self.client.force_login(self.user)

    def test_address_viewset_crud_filter_set_primary_and_isolation(self):
        list_url = reverse("main:api_address-list")

        # Create address 1 (auto primary)
        r1 = self.client.post(
            list_url,
            {
                "label": "RUMAH",
                "address": "Jl. Margonda Raya No. 10",
                "district": "Beji",
                "city": "Depok",
                "postal_code": "16424",
                "rajaongkir_destination_id": "17545",
            },
            format="json",
        )
        self.assertEqual(r1.status_code, 201)
        addr1 = r1.json()
        self.assertTrue(addr1["is_primary"])
        self.assertEqual(addr1["rajaongkir_city_id"], "115")

        # Create address 2
        r2 = self.client.post(
            list_url,
            {
                "label": "KOS",
                "address": "Jl. Cisitu Indah No. 4",
                "city": "Bandung",
                "postal_code": "40135",
            },
            format="json",
        )
        self.assertEqual(r2.status_code, 201)
        addr2_id = r2.json()["id"]

        # Filter list by label & query
        self.assertEqual(len(self.client.get(list_url, {"label": "KOS"}).json()), 1)
        self.assertEqual(len(self.client.get(list_url, {"q": "Margonda"}).json()), 1)

        # PATCH address 1 changing city clears stale district & rajaongkir_destination_id
        detail1_url = reverse("main:api_address-detail", args=[addr1["id"]])
        r_patch = self.client.patch(detail1_url, {"city": "Surabaya"}, format="json")
        self.assertEqual(r_patch.status_code, 200)
        self.assertEqual(r_patch.json()["city"], "Surabaya")
        self.assertEqual(r_patch.json()["rajaongkir_city_id"], "444")
        self.assertEqual(r_patch.json()["district"], "")
        self.assertEqual(r_patch.json()["rajaongkir_destination_id"], "")

        # Set address 2 as primary
        r_prim = self.client.post(reverse("main:api_address-set-primary", args=[addr2_id]))
        self.assertEqual(r_prim.status_code, 200)
        self.assertTrue(r_prim.json()["address"]["is_primary"])

        # Delete address 2 -> address 1 promoted back to primary
        r_del = self.client.delete(reverse("main:api_address-detail", args=[addr2_id]))
        self.assertEqual(r_del.status_code, 204)
        self.assertTrue(UserAddress.objects.get(pk=addr1["id"]).is_primary)

        # Cross-user isolation -> 404
        other_addr = UserAddress.objects.create(
            user=self.other, address="Jl. Rahasia", city="Jakarta Selatan"
        )
        self.assertEqual(
            self.client.get(reverse("main:api_address-detail", args=[other_addr.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(reverse("main:api_address-detail", args=[other_addr.pk])).status_code,
            404,
        )

    def test_profile_patch_and_preferences_patch(self):
        r_upd = self.client.patch(
            reverse("main:api_update_profile"),
            {"full_name": "Nadia Update", "phone_number": "0899887766"},
            format="json",
        )
        self.assertEqual(r_upd.status_code, 200)
        self.assertEqual(r_upd.json()["user"]["full_name"], "Nadia Update")

        r_pref = self.client.patch(
            reverse("main:api_update_preferences"),
            {"sizes": ["S", "M"], "reminder": False},
            format="json",
        )
        self.assertEqual(r_pref.status_code, 200)
        self.assertEqual(r_pref.json()["preferences"]["sizes"], ["S", "M"])
        self.assertFalse(r_pref.json()["preferences"]["reminder"])


class LembagaApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.lembaga = User.objects.create_user(
            username="panti_kasih", email="kasih@email.com", password="password123"
        )
        self.lembaga.profile.role = "LEMBAGA"  # type: ignore
        self.lembaga.profile.save()  # type: ignore

        self.other_lembaga = User.objects.create_user(
            username="sekolah_harapan", email="sekolah@email.com", password="password123"
        )
        self.other_lembaga.profile.role = "LEMBAGA"  # type: ignore
        self.other_lembaga.profile.save()  # type: ignore
        self.other_inst = InstitutionProfile.objects.create(
            user=self.other_lembaga,
            name="Sekolah Harapan",
            institution_type=InstitutionProfile.InstitutionType.SEKOLAH,
            address="Jl. Pendidikan No. 7",
            city="Bandung",
            legal_document_name="akta-rahasia.pdf",
            is_verified=True,
        )
        Kebutuhan.objects.create(
            lembaga=self.other_lembaga,
            nama_barang="Seragam SD",
            kategori="atasan",
            jumlah=10,
            status=Kebutuhan.Status.AKTIF,
        )

    def test_lembaga_profile_crud_and_cannot_self_verify(self):
        self.client.force_login(self.lembaga)
        url = reverse("main:api_lembaga_profile")

        # Belum ada profil -> exists=False, is_complete=False
        r_empty = self.client.get(url)
        self.assertEqual(r_empty.status_code, 200)
        self.assertFalse(r_empty.json()["exists"])
        self.assertFalse(r_empty.json()["is_complete"])

        # Buat profil baru (coba selipkan is_verified=True -> harus diabaikan)
        r_create = self.client.post(
            url,
            {
                "name": "Panti Kasih",
                "institution_type": "PANTI_ASUHAN",
                "address": "Jl. Mawar No. 3",
                "city": "Depok",
                "person_in_charge": "Siti",
                "contact_phone": "0811112222",
                "is_verified": True,
            },
            format="json",
        )
        self.assertEqual(r_create.status_code, 201)
        data = r_create.json()
        self.assertTrue(data["is_complete"])
        self.assertEqual(data["institution"]["rajaongkir_city_id"], "115")
        self.assertFalse(data["institution"]["is_verified"])

        # PATCH profil + email
        r_patch = self.client.patch(
            url,
            {"description": "Panti asuhan anak.", "email": "baru@kasih.org"},
            format="json",
        )
        self.assertEqual(r_patch.status_code, 200)
        self.assertEqual(r_patch.json()["institution"]["description"], "Panti asuhan anak.")
        self.assertEqual(r_patch.json()["institution"]["email"], "baru@kasih.org")

        # GET /api/profile/ untuk akun lembaga mengembalikan ringkasan lembaga
        r_prof = self.client.get(reverse("main:api_profile_data"))
        self.assertEqual(r_prof.status_code, 200)
        self.assertEqual(r_prof.json()["user"]["role"], "LEMBAGA")
        self.assertEqual(r_prof.json()["institution"]["name"], "Panti Kasih")

    def test_public_lembaga_directory_filters_and_hides_private_doc(self):
        guest = APIClient()
        list_url = reverse("main:api_lembaga-list")

        r_all = guest.get(list_url)
        self.assertEqual(r_all.status_code, 200)
        self.assertEqual(len(r_all.json()), 1)
        item = r_all.json()[0]
        self.assertEqual(item["name"], "Sekolah Harapan")
        self.assertEqual(item["active_needs_count"], 1)
        self.assertNotIn("legal_document_name", item)

        self.assertEqual(len(guest.get(list_url, {"type": "SEKOLAH"}).json()), 1)
        self.assertEqual(len(guest.get(list_url, {"type": "PANTI_ASUHAN"}).json()), 0)
        self.assertEqual(len(guest.get(list_url, {"verified": "true"}).json()), 1)
        self.assertEqual(len(guest.get(list_url, {"q": "Bandung"}).json()), 1)

        r_detail = guest.get(reverse("main:api_lembaga-detail", args=[self.other_inst.pk]))
        self.assertEqual(r_detail.status_code, 200)
        self.assertEqual(r_detail.json()["name"], "Sekolah Harapan")
