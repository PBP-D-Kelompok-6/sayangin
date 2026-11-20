from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from donasi.models import Kebutuhan, Penawaran
from main.models import UserProfile, InstitutionProfile


class DonasiAPITest(APITestCase):
    def setUp(self):
        # 1. Akun Lembaga
        self.user_lembaga = User.objects.create_user(username="lembaga_test", password="password123")
        UserProfile.objects.update_or_create(user=self.user_lembaga, defaults={"role": "LEMBAGA"})
        InstitutionProfile.objects.update_or_create(user=self.user_lembaga,defaults={"name": "Panti Asuhan Sejahtera"},)

        # 2. Akun Donatur
        self.user_donatur = User.objects.create_user(username="donatur_test", password="password123")
        UserProfile.objects.update_or_create(user=self.user_donatur, defaults={"role": "PERSONAL"})

        # 3. Kebutuhan Awal
        self.kebutuhan = Kebutuhan.objects.create(
            lembaga=self.user_lembaga,
            nama_barang="Pakaian Bayi",
            kategori="atasan",
            jumlah=10,
            status=Kebutuhan.Status.AKTIF,
        )

        self.url_kebutuhan_list = reverse("donasi:donasi_api:kebutuhan_list")
        self.url_kebutuhan_detail = reverse("donasi:donasi_api:kebutuhan_detail", args=[self.kebutuhan.pk])
        self.url_penawaran_list = reverse("donasi:donasi_api:penawaran_list")

    def test_publik_bisa_melihat_daftar_kebutuhan(self):
        response = self.client.get(self.url_kebutuhan_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_donatur_tidak_bisa_buat_kebutuhan(self):
        self.client.force_authenticate(user=self.user_donatur)
        payload = {"nama_barang": "Jaket", "jumlah": 3}
        response = self.client.post(self.url_kebutuhan_list, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_lembaga_bisa_buat_kebutuhan(self):
        self.client.force_authenticate(user=self.user_lembaga)
        payload = {"nama_barang": "Baju Sekolah", "jumlah": 5, "kategori": "atasan"}
        response = self.client.post(self.url_kebutuhan_list, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_donatur_bisa_kirim_penawaran(self):
        self.client.force_authenticate(user=self.user_donatur)
        payload = {
            "kebutuhan": self.kebutuhan.pk,
            "nama_barang": "Baju Bayi Katun",
            "jumlah": 2,
            "metode": "antar",
            "jam": "pagi",
        }
        response = self.client.post(self.url_penawaran_list, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)