from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from impact import sources
from impact.models import Challenge
from impact.tests import FAKE, add, make_user


# API untuk Flutter (impact/api.py); SOURCES diganti FAKE seperti di tests.py
@patch.dict(sources.SOURCES, FAKE)
class ImpactApiTest(APITestCase):
    def setUp(self):
        self.user = make_user("rania")
        # enforce_csrf_checks: memastikan API tetap jalan tanpa token CSRF (seperti dari Flutter)
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.today = timezone.localdate()

    def make_challenge(self, owner=None, **kwargs):
        data = {"title": "Donasi 3 barang", "kind": "donasi", "target": 3,
                "start_date": self.today, "end_date": self.today + timedelta(days=7)}
        data.update(kwargs)
        return Challenge.objects.create(owner=owner or self.user, **data)

    # dashboard: angka & poin sama dengan web, gambar lencana jadi URL lengkap
    def test_dashboard(self):
        add(self.user, "donasi", times=2)
        self.make_challenge()
        response = self.client.get(reverse("impact:api_dashboard"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["period"], "bulan")
        self.assertEqual(data["points"], 2 * sources.POINTS["donasi"])
        self.assertTrue(data["badges"][0]["image"].startswith("http://testserver/static/"))
        self.assertEqual(data["leaderboard"][0]["username"], "rania")
        self.assertEqual(data["next_step"]["done"], 2)
        self.assertEqual(data["next_step"]["remaining"], 1)
        self.assertEqual(data["challenge_total"], 1)

    def test_dashboard_periode_semua(self):
        add(self.user, "donasi", days_ago=60)
        self.assertEqual(self.client.get(reverse("impact:api_dashboard")).json()["points"], 0)
        data = self.client.get(reverse("impact:api_dashboard"), {"periode": "semua"}).json()
        self.assertEqual(data["period"], "semua")
        self.assertEqual(data["points"], sources.POINTS["donasi"])

    # dashboard & tantangan hanya untuk akun personal yang login
    def test_tamu_dan_lembaga_ditolak(self):
        guest = APIClient()
        self.assertEqual(guest.get(reverse("impact:api_dashboard")).status_code, 403)
        self.assertEqual(guest.get(reverse("impact:api_challenge-list")).status_code, 403)
        guest.force_login(make_user("panti", role="LEMBAGA"))
        self.assertEqual(guest.get(reverse("impact:api_dashboard")).status_code, 403)
        self.assertEqual(guest.get(reverse("impact:api_challenge-list")).status_code, 403)

    # peringkat: tamu boleh lihat, tapi nama disamarkan dan id user tidak terkirim
    def test_peringkat_tamu(self):
        add(self.user, "donasi")
        data = APIClient().get(reverse("impact:api_leaderboard")).json()
        self.assertEqual(data["leaderboard"], [{"rank": 1, "username": "r***a", "points": 20}])
        self.assertIsNone(data["my_rank"])

    def test_peringkat_login(self):
        add(self.user, "donasi")
        add(make_user("ira"), "lemari")
        data = self.client.get(reverse("impact:api_leaderboard")).json()
        self.assertEqual([row["username"] for row in data["leaderboard"]], ["rania", "ira"])
        self.assertTrue(data["leaderboard"][0]["is_me"])
        self.assertEqual(data["my_rank"]["rank"], 1)

    # daftar tantangan: hanya milik sendiri, filter jenis & status sama dengan web
    def test_daftar_dan_filter(self):
        self.make_challenge(title="A")
        self.make_challenge(title="B", kind="lemari", start_date=self.today - timedelta(days=10),
                            end_date=self.today - timedelta(days=1))
        self.make_challenge(owner=make_user("ira"), title="C")
        url = reverse("impact:api_challenge-list")
        self.assertEqual(sorted(row["title"] for row in self.client.get(url).json()), ["A", "B"])
        self.assertEqual([row["title"] for row in self.client.get(url, {"jenis": "lemari"}).json()], ["B"])
        self.assertEqual([row["title"] for row in self.client.get(url, {"status": "berjalan"}).json()], ["A"])
        self.assertEqual([row["title"] for row in self.client.get(url, {"status": "berakhir"}).json()], ["B"])

    def test_tambah(self):
        response = self.client.post(reverse("impact:api_challenge-list"), {
            "title": "Catat 5 barang", "kind": "lemari", "target": 5,
            "start_date": str(self.today), "end_date": str(self.today + timedelta(days=3)),
            "owner": 999}, format="json")
        self.assertEqual(response.status_code, 201)
        challenge = Challenge.objects.get()
        self.assertEqual(challenge.owner, self.user) # owner dari input diabaikan
        self.assertEqual(response.json()["kind_label"], "Barang dicatat di lemari")

    def test_validasi(self):
        url = reverse("impact:api_challenge-list")
        response = self.client.post(url, {"title": "X", "kind": "donasi", "target": 0,
                                          "start_date": str(self.today), "end_date": str(self.today)}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("target", response.json())
        response = self.client.post(url, {"title": "X", "kind": "donasi", "target": 1, "start_date": str(self.today),
                                          "end_date": str(self.today - timedelta(days=1))}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("end_date", response.json())
        self.assertFalse(Challenge.objects.exists())

    def test_detail_ubah_hapus(self):
        challenge = self.make_challenge()
        url = reverse("impact:api_challenge-detail", args=[challenge.pk])
        self.assertEqual(self.client.get(url).json()["title"], "Donasi 3 barang")
        response = self.client.patch(url, {"target": 5}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["target"], 5)
        # PATCH tanggal selesai saja tetap divalidasi terhadap tanggal mulai yang lama
        response = self.client.patch(url, {"end_date": str(self.today - timedelta(days=1))}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(Challenge.objects.exists())

    # tantangan milik orang lain -> 404 untuk lihat, ubah, dan hapus
    def test_milik_orang_lain(self):
        challenge = self.make_challenge(owner=make_user("ira"))
        url = reverse("impact:api_challenge-detail", args=[challenge.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, {"target": 9}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(Challenge.objects.exists())
