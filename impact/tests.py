from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from impact import sources, views
from impact.models import Challenge

# SOURCES palsu: semua jenis aksi dibaca dari LogEntry, dibedakan lewat object_repr (mis. "donasi")
FAKE = {key: {"model": "admin.LogEntry", "user": "user", "date": "action_time", "filter": {"object_repr": key}}
        for key in sources.SOURCES}


# Buat user untuk test; role-nya disimpan di profile milik tim (PERSONAL / LEMBAGA)
def make_user(username, role="PERSONAL"):
    user = User.objects.create_user(username=username, password="pass12345")
    user.profile.role = role
    user.profile.save()
    return user


def add(user, key, days_ago=0, times=1):
    """Pura-pura user melakukan aksi `key` (mis. donasi) sebanyak `times` kali."""
    for _ in range(times):
        entry = LogEntry.objects.create(user=user, object_repr=key, action_flag=1)
        # action_time otomatis "sekarang", jadi diubah manual supaya bisa pura-pura aksi di masa lalu
        LogEntry.objects.filter(pk=entry.pk).update(action_time=timezone.now() - timedelta(days=days_ago))


# hitungan (sources.py & lencana) :3
@patch.dict(sources.SOURCES, FAKE) # selama test kelas ini, SOURCES diganti FAKE
class HitunganTest(TestCase):
    def setUp(self):
        self.user = make_user("rania")

    # since membatasi tanggal: donasi 60 hari lalu tidak ikut kalau batasnya 30 hari terakhir
    def test_hitung_dan_periode(self):
        add(self.user, "donasi")
        add(self.user, "donasi", days_ago=60)
        self.assertEqual(sources.count_for_user("donasi", self.user), 2)
        self.assertEqual(sources.count_for_user("donasi", self.user, since=timezone.now() - timedelta(days=30)), 1)

    # model teman yang belum ada tidak bikin error, hasilnya 0
    def test_modul_teman_belum_ada(self):
        with patch.dict(sources.SOURCES, {"lemari": {"model": "lemari.Belum", "user": "u", "date": "d", "filter": {}}}):
            self.assertEqual(sources.count_for_user("lemari", self.user), 0)
            self.assertEqual(sources.count_per_user("lemari"), {})  # versi semua user juga tidak error

    # hitung aksi semua user sekaligus: hasilnya {id_user: jumlah}, bisa dibatasi periode
    def test_hitung_per_user(self):
        ira = make_user("ira")
        add(self.user, "donasi", times=2)
        add(ira, "donasi")
        add(ira, "donasi", days_ago=60)
        self.assertEqual(sources.count_per_user("donasi"), {self.user.id: 2, ira.id: 2})
        self.assertEqual(sources.count_per_user("donasi", since=timezone.now() - timedelta(days=30)),
                         {self.user.id: 2, ira.id: 1})  # donasi ira 60 hari lalu tidak ikut
        self.assertEqual(sources.count_per_user("terjual"), {})  # belum ada yang menjual

    # lencana diraih sesuai jumlah aksi, progres dalam persen, dan tiap lencana punya gambar
    def test_lencana(self):
        add(self.user, "lemari")
        add(self.user, "donasi", times=2)
        badges = views.get_badges(views.get_counts(self.user))
        self.assertEqual([b["name"] for b in badges if b["earned"]], ["Sayangin Starter", "First Giving"])
        self.assertEqual(badges[4]["percent"], 67)  # Kind Closet: 2 dari 3
        self.assertEqual(badges[3]["image"], "img/lencana-donatur.jpg")  # First Giving


# dashboard & JSON :3
@patch.dict(sources.SOURCES, FAKE)
class DashboardTest(TestCase):
    # data awal: 1 terjual (+10), 1 donasi (+20), 1 lemari 400 hari lalu (+2, hanya terhitung "sepanjang waktu")
    def setUp(self):
        self.user = make_user("rania")
        add(self.user, "terjual")
        add(self.user, "donasi")
        add(self.user, "lemari", days_ago=400)

    # belum login -> dialihkan ke login (302); akun lembaga -> ditolak (403)
    def test_harus_login_dan_bukan_lembaga(self):
        url = reverse("impact:show_impact_dashboard")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(make_user("panti", role="LEMBAGA"))
        self.assertEqual(self.client.get(url).status_code, 403)

    # halaman penuh memakai base.html; request HTMX hanya dibalas potongan summary.html
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

    # langkah berikutnya = tantangan berjalan yang belum selesai dengan sisa paling sedikit
    def test_langkah_berikutnya(self):
        self.client.force_login(self.user)
        url = reverse("impact:show_impact_dashboard")
        self.assertIsNone(self.client.get(url).context["next_step"])
        today = timezone.localdate()
        Challenge.objects.create(owner=self.user, title="Jual 2", kind="terjual", target=2, start_date=today, end_date=today)
        Challenge.objects.create(owner=self.user, title="Donasi 1", kind="donasi", target=1, start_date=today, end_date=today)
        self.assertEqual(self.client.get(url).context["next_step"]["challenge"].title, "Jual 2")  # sisa 1; Donasi 1 sudah selesai

    # tantangan kamu = hanya yang berjalan & belum selesai, urut deadline terdekat, maksimal 4
    def test_tantangan_kamu(self):
        self.client.force_login(self.user)
        url = reverse("impact:show_impact_dashboard")
        today = timezone.localdate()
        for i in range(5):  # 5 tantangan lemari, deadline-nya 5, 4, 3, 2, 1 hari lagi
            Challenge.objects.create(owner=self.user, title=f"Lemari {5 - i}", kind="lemari", target=3,
                                     start_date=today, end_date=today + timedelta(days=5 - i))
        Challenge.objects.create(owner=self.user, title="Sudah lewat", kind="lemari", target=3,
                                 start_date=today - timedelta(days=9), end_date=today - timedelta(days=1))
        Challenge.objects.create(owner=self.user, title="Sudah selesai", kind="donasi", target=1,
                                 start_date=today, end_date=today)  # donasi hari ini sudah 1 -> selesai
        context = self.client.get(url).context
        self.assertEqual([row["challenge"].title for row in context["challenges"]],
                         ["Lemari 1", "Lemari 2", "Lemari 3", "Lemari 4"])  # "Lemari 5" tidak muat, lewat & selesai tidak ikut
        self.assertEqual(context["challenge_total"], 7)  # semua tantangan milik user, termasuk yang lewat & selesai

    # /dampak/json/ berisi data yang sama dengan dashboard
    def test_json(self):
        self.client.force_login(self.user)
        data = self.client.get(reverse("impact:show_impact_json")).json()
        self.assertEqual(data["points"], 30)
        self.assertEqual(len(data["badges"]), 6)


# CRUD tantangan pribadi :3
@patch.dict(sources.SOURCES, FAKE)
class ChallengeCrudTest(TestCase):
    # 2 tantangan milik rania (berjalan & sudah berakhir) + 1 milik user lain
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

    # CREATE: tersimpan, lalu dialihkan ke daftar; pemiliknya otomatis user yang login
    def test_create(self):
        url = reverse("impact:create_impact_challenge")
        self.assertEqual(self.client.get(url).status_code, 200)
        today = timezone.localdate()
        response = self.client.post(url, {"title": "Catat 5 barang", "kind": "lemari", "target": 5,
                                          "start_date": today, "end_date": today})
        self.assertRedirects(response, reverse("impact:show_impact_challenges"))
        self.assertEqual(Challenge.objects.get(title="Catat 5 barang").owner, self.user)

    # form tidak valid: pesan error tampil dan data tidak tersimpan
    def test_create_tidak_valid(self):
        today = timezone.localdate()
        response = self.client.post(reverse("impact:create_impact_challenge"),
                                    {"title": "Salah", "kind": "lemari", "target": 0,
                                     "start_date": today, "end_date": today - timedelta(days=1)})
        self.assertContains(response, "Target minimal 1.")
        self.assertContains(response, "Tanggal selesai tidak boleh sebelum tanggal mulai.")
        self.assertFalse(Challenge.objects.filter(title="Salah").exists())

    # READ: hanya milik sendiri, progres terhitung, filter jenis & status (biasa maupun HTMX)
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

    # UPDATE: form terisi data lama, lalu perubahan tersimpan
    def test_update(self):
        url = reverse("impact:edit_impact_challenge", args=[self.mine.pk])
        self.assertContains(self.client.get(url), "Jual 3")
        data = {"title": "Jual 4", "kind": "terjual", "target": 4,
                "start_date": self.mine.start_date, "end_date": self.mine.end_date}
        self.assertRedirects(self.client.post(url, data), reverse("impact:show_impact_challenges"))
        self.mine.refresh_from_db()
        self.assertEqual(str(self.mine), "Jual 4")

    # DELETE: hanya lewat POST; lewat HTMX balasannya kosong, tanpa HTMX dialihkan ke daftar
    def test_delete(self):
        url = reverse("impact:delete_impact_challenge", args=[self.mine.pk])
        self.assertEqual(self.client.get(url).status_code, 405)  # hapus hanya lewat POST
        self.assertEqual(self.client.post(url, HTTP_HX_REQUEST="true").content, b"")
        self.assertRedirects(self.client.post(reverse("impact:delete_impact_challenge", args=[self.old.pk])),
                             reverse("impact:show_impact_challenges"))
        self.assertFalse(Challenge.objects.filter(owner=self.user).exists())

    # tantangan milik orang lain tidak bisa diubah atau dihapus (404)
    def test_milik_orang_lain_tidak_bisa_diubah(self):
        self.assertEqual(self.client.get(reverse("impact:edit_impact_challenge", args=[self.theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("impact:delete_impact_challenge", args=[self.theirs.pk])).status_code, 404)