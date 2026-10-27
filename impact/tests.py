"""Unit test Modul E.  Jalankan:  python manage.py test impact

Model teman belum semuanya ada, jadi SOURCES diarahkan sementara ke tabel bawaan
Django `admin.LogEntry` (punya kolom user & action_time). Jenis aksi dibedakan lewat object_repr.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from impact import sources, views
from impact.models import Challenge

FAKE = {key: {"model": "admin.LogEntry", "user": "user", "date": "action_time", "filter": {"object_repr": key}}
        for key in sources.SOURCES}


def make_user(username, role="PERSONAL"):
    user = User.objects.create_user(username=username, password="pass12345")
    user.profile.role = role
    user.profile.save()
    return user


def add(user, key, days_ago=0, times=1):
    """Pura-pura user melakukan aksi `key` (mis. donasi) sebanyak `times` kali."""
    for _ in range(times):
        entry = LogEntry.objects.create(user=user, object_repr=key, action_flag=1)
        LogEntry.objects.filter(pk=entry.pk).update(action_time=timezone.now() - timedelta(days=days_ago))


@patch.dict(sources.SOURCES, FAKE)
class HitunganTest(TestCase):
    def setUp(self):
        self.user = make_user("rania")

    def test_hitung_dan_periode(self):
        add(self.user, "donasi")
        add(self.user, "donasi", days_ago=60)
        self.assertEqual(sources.count_for_user("donasi", self.user), 2)
        self.assertEqual(sources.count_for_user("donasi", self.user, since=timezone.now() - timedelta(days=30)), 1)

    def test_modul_teman_belum_ada(self):
        with patch.dict(sources.SOURCES, {"lemari": {"model": "lemari.Belum", "user": "u", "date": "d", "filter": {}}}):
            self.assertEqual(sources.count_for_user("lemari", self.user), 0)

    def test_lencana(self):
        add(self.user, "lemari")
        add(self.user, "donasi", times=2)
        badges = views.get_badges(views.get_counts(self.user))
        self.assertEqual([b["name"] for b in badges if b["earned"]], ["Sayangin Starter", "First Giving"])
        self.assertEqual(badges[4]["percent"], 67)  # Kind Closet: 2 dari 3


@patch.dict(sources.SOURCES, FAKE)
class DashboardTest(TestCase):
    def setUp(self):
        self.user = make_user("rania")
        add(self.user, "terjual")
        add(self.user, "donasi")
        add(self.user, "lemari", days_ago=400)

    def test_harus_login_dan_bukan_lembaga(self):
        url = reverse("impact:show_impact_dashboard")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(make_user("panti", role="LEMBAGA"))
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_dashboard_dan_filter_periode_htmx(self):
        self.client.force_login(self.user)
        url = reverse("impact:show_impact_dashboard")
        response = self.client.get(url)
        self.assertTemplateUsed(response, "base.html")  # memakai base.html milik tim
        self.assertEqual(response.context["points"], 30)  # 10 + 20 (lemari 400 hari lalu tidak dihitung)
        response = self.client.get(url + "?periode=semua", HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "impact/partials/summary.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertEqual(response.context["points"], 32)

    def test_langkah_berikutnya(self):
        self.client.force_login(self.user)
        url = reverse("impact:show_impact_dashboard")
        self.assertIsNone(self.client.get(url).context["next_step"])
        today = timezone.localdate()
        Challenge.objects.create(owner=self.user, title="Jual 2", kind="terjual", target=2, start_date=today, end_date=today)
        Challenge.objects.create(owner=self.user, title="Donasi 1", kind="donasi", target=1, start_date=today, end_date=today)
        self.assertEqual(self.client.get(url).context["next_step"]["challenge"].title, "Jual 2")  # sisa 1; Donasi 1 sudah selesai

    def test_json(self):
        self.client.force_login(self.user)
        data = self.client.get(reverse("impact:show_impact_json")).json()
        self.assertEqual(data["points"], 30)
        self.assertEqual(len(data["badges"]), 6)


@patch.dict(sources.SOURCES, FAKE)
class ChallengeCrudTest(TestCase):
    def setUp(self):
        self.user = make_user("rania")
        self.client.force_login(self.user)
        today = timezone.localdate()
        self.mine = Challenge.objects.create(owner=self.user, title="Jual 3", kind="terjual", target=3,
                                             start_date=today, end_date=today + timedelta(days=7))
        self.old = Challenge.objects.create(owner=self.user, title="Donasi lama", kind="donasi", target=1,
                                            start_date=today - timedelta(days=20), end_date=today - timedelta(days=10))
        self.theirs = Challenge.objects.create(owner=make_user("ira"), title="Punya Ira", kind="donasi", target=1,
                                               start_date=today, end_date=today)

    def test_create(self):
        url = reverse("impact:create_impact_challenge")
        self.assertEqual(self.client.get(url).status_code, 200)
        today = timezone.localdate()
        response = self.client.post(url, {"title": "Catat 5 barang", "kind": "lemari", "target": 5,
                                          "start_date": today, "end_date": today})
        self.assertRedirects(response, reverse("impact:show_impact_challenges"))
        self.assertEqual(Challenge.objects.get(title="Catat 5 barang").owner, self.user)

    def test_create_tidak_valid(self):
        today = timezone.localdate()
        response = self.client.post(reverse("impact:create_impact_challenge"),
                                    {"title": "Salah", "kind": "lemari", "target": 0,
                                     "start_date": today, "end_date": today - timedelta(days=1)})
        self.assertContains(response, "Target minimal 1.")
        self.assertContains(response, "Tanggal selesai tidak boleh sebelum tanggal mulai.")
        self.assertFalse(Challenge.objects.filter(title="Salah").exists())

    def test_read_dan_filter(self):
        add(self.user, "terjual")
        url = reverse("impact:show_impact_challenges")
        response = self.client.get(url)
        self.assertEqual([r["challenge"].title for r in response.context["rows"]], ["Jual 3", "Donasi lama"])
        self.assertEqual(response.context["rows"][0]["done"], 1)
        self.assertNotContains(response, "Punya Ira")
        response = self.client.get(url + "?jenis=donasi&status=berakhir", HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "impact/partials/challenge_list.html")
        self.assertEqual([r["challenge"].title for r in response.context["rows"]], ["Donasi lama"])
        response = self.client.get(url + "?status=berjalan")
        self.assertEqual([r["challenge"].title for r in response.context["rows"]], ["Jual 3"])

    def test_update(self):
        url = reverse("impact:edit_impact_challenge", args=[self.mine.pk])
        self.assertContains(self.client.get(url), "Jual 3")
        data = {"title": "Jual 4", "kind": "terjual", "target": 4,
                "start_date": self.mine.start_date, "end_date": self.mine.end_date}
        self.assertRedirects(self.client.post(url, data), reverse("impact:show_impact_challenges"))
        self.mine.refresh_from_db()
        self.assertEqual(str(self.mine), "Jual 4")

    def test_delete(self):
        url = reverse("impact:delete_impact_challenge", args=[self.mine.pk])
        self.assertEqual(self.client.get(url).status_code, 405)  # hapus hanya lewat POST
        self.assertEqual(self.client.post(url, HTTP_HX_REQUEST="true").content, b"")
        self.assertRedirects(self.client.post(reverse("impact:delete_impact_challenge", args=[self.old.pk])),
                             reverse("impact:show_impact_challenges"))
        self.assertFalse(Challenge.objects.filter(owner=self.user).exists())

    def test_milik_orang_lain_tidak_bisa_diubah(self):
        self.assertEqual(self.client.get(reverse("impact:edit_impact_challenge", args=[self.theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("impact:delete_impact_challenge", args=[self.theirs.pk])).status_code, 404)