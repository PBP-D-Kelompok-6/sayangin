import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from donasi.forms import KebutuhanForm, PenawaranForm
from donasi.models import (
    Kategori,
    Kondisi,
    Kebutuhan,
    Penawaran,
    _kondisi_yang_memenuhi,
)
from donasi.permissions import LEMBAGA_GROUP, is_lembaga
from donasi.views import _label_kondisi, urutkan_kebutuhan

User = get_user_model()
HX_HEADERS = {"HTTP_HX_REQUEST": "true"}


def besok(hari=1):
    return timezone.localdate() + datetime.timedelta(days=hari)


class DonasiBaseTestCase(TestCase):
    def setUp(self):
        self.grup = Group.objects.create(name=LEMBAGA_GROUP)

        # Akun Donatur
        self.donatur = User.objects.create_user("sekar", password="rahasia123")

        # Akun Lembaga
        self.lembaga = User.objects.create_user(
            "panti-a", password="rahasia123", first_name="Panti A"
        )
        self.lembaga.groups.add(self.grup)

        self.lembaga2 = User.objects.create_user(
            "panti-b", password="rahasia123", first_name="Panti B"
        )
        self.lembaga2.groups.add(self.grup)

        # Data Kebutuhan
        self.jaket = Kebutuhan.objects.create(
            lembaga=self.lembaga,
            nama_barang="Jaket anak",
            kategori=Kategori.PAKAIAN_LUARAN,
            jumlah=12,
            terpenuhi=3,
            ukuran="6 th,8 th",
            kondisi_min=Kondisi.TERAWAT,
            tenggat=besok(30),
            status=Kebutuhan.Status.AKTIF,
        )

        self.sepatu = Kebutuhan.objects.create(
            lembaga=self.lembaga2,
            nama_barang="Sepatu sekolah",
            kategori=Kategori.ALAS_KAKI,
            jumlah=20,
            terpenuhi=15,
            kondisi_min=Kondisi.SEPERTI_BARU,
            tenggat=besok(10),
            status=Kebutuhan.Status.AKTIF,
        )

        self.draf = Kebutuhan.objects.create(
            lembaga=self.lembaga,
            nama_barang="Draf rahasia",
            kategori=Kategori.BUKU,
            jumlah=5,
            status=Kebutuhan.Status.DRAFT,
        )

    def buat_tawaran(self, **kwargs):
        data = {
            "donatur": self.donatur,
            "lembaga": self.lembaga,
            "kebutuhan": self.jaket,
            "nama_barang": "Jaket kulit",
            "jumlah": 2,
            "kondisi": Kondisi.TERAWAT,
            "tanggal_rencana": besok(),
        }
        data.update(kwargs)
        return Penawaran.objects.create(**data)


class ModelTest(DonasiBaseTestCase):
    def test_properti_kebutuhan(self):
        self.assertEqual(self.jaket.sisa, 9)
        self.assertEqual(self.jaket.persen, 25)
        self.assertEqual(self.jaket.ukuran_list, ["6 th", "8 th"])
        self.assertEqual(self.jaket.ukuran_label, "6 th, 8 th")
        self.assertEqual(self.jaket.nama_lembaga, "Panti A")
        self.assertEqual(str(self.jaket), "Jaket anak (3/12)")
        self.assertFalse(self.jaket.kedaluwarsa)

        # Test kasus sisa, persen 0 & kedaluwarsa
        k_nol = Kebutuhan(jumlah=0, terpenuhi=0, tenggat=besok(-1))
        self.assertEqual(k_nol.persen, 0)
        self.assertTrue(k_nol.kedaluwarsa)

        # Test nama_lembaga jika first_name kosong
        user_no_name = User.objects.create_user("lembaga_anon")
        k_anon = Kebutuhan(lembaga=user_no_name)
        self.assertEqual(k_anon.nama_lembaga, "lembaga_anon")

    def test_properti_penawaran(self):
        p = self.buat_tawaran()
        self.assertEqual(p.nama_donatur, "sekar")
        self.assertIn("Jaket kulit", str(p))

    def test_kondisi_yang_memenuhi(self):
        self.assertIn(Kondisi.TERAWAT, _kondisi_yang_memenuhi(Kondisi.SEPERTI_BARU))
        self.assertIn(Kondisi.SEPERTI_BARU, _kondisi_yang_memenuhi(Kondisi.SEPERTI_BARU))
        self.assertEqual(_kondisi_yang_memenuhi(Kondisi.ADA_CACAT), [])
        self.assertEqual(_kondisi_yang_memenuhi("invalid"), [])

    def test_aktif_hanya_yang_tayang_belum_lewat_dan_belum_penuh(self):
        Kebutuhan.objects.create(
            lembaga=self.lembaga,
            nama_barang="Lewat",
            jumlah=3,
            tenggat=besok(-1),
            status=Kebutuhan.Status.AKTIF,
        )
        Kebutuhan.objects.create(
            lembaga=self.lembaga,
            nama_barang="Penuh",
            jumlah=3,
            terpenuhi=3,
            status=Kebutuhan.Status.AKTIF,
        )
        nama = set(Kebutuhan.objects.aktif().values_list("nama_barang", flat=True))
        self.assertEqual(nama, {"Jaket anak", "Sepatu sekolah"})

    def test_cocok_dengan_kategori_ukuran_kondisi(self):
        self.assertEqual(
            Kebutuhan.objects.cocok_dengan(kategori="pakaian-luaran"), [self.jaket]
        )
        self.assertEqual(
            Kebutuhan.objects.cocok_dengan(kategori="pakaian-luaran", ukuran="8 th"),
            [self.jaket],
        )
        self.assertEqual(
            Kebutuhan.objects.cocok_dengan(kategori="pakaian-luaran", ukuran="XL"), []
        )
        self.assertEqual(
            Kebutuhan.objects.cocok_dengan(kategori="alas-kaki", kondisi="terawat"), []
        )
        self.assertEqual(
            Kebutuhan.objects.cocok_dengan(kategori="alas-kaki", kondisi="seperti-baru"),
            [self.sepatu],
        )

    def test_alur_status_penawaran(self):
        p = self.buat_tawaran()
        self.assertTrue(p.terima())
        self.assertEqual(p.status, Penawaran.Status.DITERIMA)
        self.assertFalse(p.tolak())  
        self.assertTrue(p.selesaikan())
        self.jaket.refresh_from_db()
        self.assertEqual(self.jaket.terpenuhi, 5)
        self.assertIsNotNone(p.diterima_pada)

    def test_tolak_penawaran(self):
        p = self.buat_tawaran()
        self.assertTrue(p.tolak())
        self.assertEqual(p.status, Penawaran.Status.DITOLAK)
        self.assertFalse(p.terima())

    def test_selesaikan_butuh_status_diterima(self):
        p = self.buat_tawaran()
        self.assertFalse(p.selesaikan())
        self.jaket.refresh_from_db()
        self.assertEqual(self.jaket.terpenuhi, 3)

    def test_kebutuhan_selesai_otomatis_saat_penuh(self):
        p = self.buat_tawaran(jumlah=9)
        p.terima()
        p.selesaikan()
        self.jaket.refresh_from_db()
        self.assertEqual(self.jaket.status, Kebutuhan.Status.SELESAI)


class FormTest(DonasiBaseTestCase):
    def data_kebutuhan(self, **kwargs):
        data = {
            "nama_barang": "Tas sekolah",
            "kategori": Kategori.PERLENGKAPAN_SEKOLAH,
            "jumlah": 5,
            "ukuran": [],
            "kondisi_min": Kondisi.TERAWAT,
            "tenggat": besok(5).isoformat(),
            "cerita": "Butuh tas",
        }
        data.update(kwargs)
        return data

    def data_penawaran(self, **kwargs):
        data = {
            "nama_barang": "Jaket kulit",
            "jumlah": 2,
            "ukuran": "8 th",
            "kondisi": Kondisi.TERAWAT,
            "metode": Penawaran.Metode.ANTAR,
            "tanggal_rencana": besok().isoformat(),
            "jam": Penawaran.Jam.PAGI,
            "pesan": "Siap antar",
            "bersih": True,
        }
        data.update(kwargs)
        return data

    def test_kebutuhan_form_valid(self):
        form = KebutuhanForm(self.data_kebutuhan(ukuran=["S", "M"]))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["ukuran"], "S,M")

    def test_kebutuhan_form_initial_ukuran(self):
        form = KebutuhanForm(instance=self.jaket)
        self.assertEqual(form.initial["ukuran"], ["6 th", "8 th"])

    def test_tenggat_masa_lalu_ditolak(self):
        form = KebutuhanForm(self.data_kebutuhan(tenggat=besok(-2).isoformat()))
        self.assertFalse(form.is_valid())
        self.assertIn("tenggat", form.errors)

    def test_jumlah_kurang_dari_terpenuhi_ditolak(self):
        form = KebutuhanForm(self.data_kebutuhan(jumlah=2), instance=self.jaket)
        self.assertFalse(form.is_valid())
        self.assertIn("jumlah", form.errors)

    def test_penawaran_form_valid(self):
        form = PenawaranForm(self.data_penawaran(), kebutuhan=self.jaket)
        self.assertTrue(form.is_valid(), form.errors)

    def test_penawaran_wajib_bersih(self):
        data = self.data_penawaran()
        del data["bersih"]
        form = PenawaranForm(data, kebutuhan=self.jaket)
        self.assertFalse(form.is_valid())
        self.assertIn("bersih", form.errors)

    def test_penawaran_tanggal_masa_lalu_ditolak(self):
        data = self.data_penawaran(tanggal_rencana=besok(-2).isoformat())
        form = PenawaranForm(data, kebutuhan=self.jaket)
        self.assertFalse(form.is_valid())
        self.assertIn("tanggal_rencana", form.errors)

    def test_penawaran_tanggal_melebihi_tenggat_ditolak(self):
        data = self.data_penawaran(tanggal_rencana=besok(40).isoformat())
        form = PenawaranForm(data, kebutuhan=self.jaket)
        self.assertFalse(form.is_valid())
        self.assertIn("tanggal_rencana", form.errors)


class PermissionsAndHelpersTest(DonasiBaseTestCase):
    def test_is_lembaga(self):
        self.assertTrue(is_lembaga(self.lembaga))
        self.assertFalse(is_lembaga(self.donatur))

    def test_label_kondisi(self):
        self.assertEqual(_label_kondisi(Kondisi.SEPERTI_BARU), "Seperti baru")
        self.assertEqual(_label_kondisi("invalid"), "")

    def test_urutkan_kebutuhan(self):
        k_tanpa_tenggat = Kebutuhan.objects.create(
            lembaga=self.lembaga, nama_barang="Tanpa Tenggat", jumlah=5
        )
        daftar = [self.jaket, self.sepatu, k_tanpa_tenggat]

        # Urut berdasarkan progres
        sorted_progres = urutkan_kebutuhan(daftar, "progres")
        self.assertEqual(sorted_progres[0], k_tanpa_tenggat)
        self.assertEqual(sorted_progres[1], self.jaket)

        # Urut berdasarkan terbaru
        sorted_terbaru = urutkan_kebutuhan(daftar, "terbaru")
        self.assertEqual(sorted_terbaru[0], k_tanpa_tenggat)

        # Urut berdasarkan tenggat (default)
        sorted_tenggat = urutkan_kebutuhan(daftar, "tenggat")
        self.assertEqual(sorted_tenggat[0], self.sepatu)


class SisiDonaturTest(DonasiBaseTestCase):
    def test_anonim_dialihkan_ke_login(self):
        response = self.client.get(reverse("donasi:pilih_lembaga"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_lembaga_tidak_boleh_mendonasikan(self):
        self.client.force_login(self.lembaga)
        response = self.client.get(reverse("donasi:pilih_lembaga"))
        self.assertRedirects(response, reverse("donasi:dashboard_lembaga"))

        response_kirim = self.client.get(reverse("donasi:kirim_donasi", args=[self.jaket.pk]))
        self.assertEqual(response_kirim.status_code, 403)

    def test_link_profil_mobile_tidak_404(self):
        self.client.force_login(self.donatur)
        response = self.client.get(reverse("donasi:tawaran_saya"))
        self.assertContains(response, f'class="avatar-link" href="{reverse("main:show_profile")}"')

    def test_pilih_lembaga_menampilkan_kebutuhan_cocok(self):
        self.client.force_login(self.donatur)
        response = self.client.get(
            reverse("donasi:pilih_lembaga"),
            {"nama": "Jaket", "kategori": "pakaian-luaran"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "donasi/pilih_lembaga.html")
        self.assertContains(response, "Panti A")
        self.assertNotContains(response, "Panti B")

    def test_pilih_lembaga_htmx_partial(self):
        self.client.force_login(self.donatur)
        response = self.client.get(
            reverse("donasi:pilih_lembaga"),
            {"urut": "progres"},
            **HX_HEADERS,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "donasi/_org_list.html")

    def test_kirim_donasi_get_tanpa_nama_barang_redirect(self):
        self.client.force_login(self.donatur)
        response = self.client.get(
            reverse("donasi:kirim_donasi", args=[self.jaket.pk])
        )
        self.assertRedirects(response, reverse("donasi:pilih_lembaga"))

    def test_kirim_donasi_get_dengan_nama_barang(self):
        self.client.force_login(self.donatur)
        response = self.client.get(
            reverse("donasi:kirim_donasi", args=[self.jaket.pk]),
            {"nama": "Jaket Kulit", "kondisi": "terawat", "foto": "https://example.com/foto.jpg"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jaket Kulit")

    def test_kirim_donasi_kebutuhan_draf_404(self):
        self.client.force_login(self.donatur)
        response = self.client.get(
            reverse("donasi:kirim_donasi", args=[self.draf.pk]),
            {"nama": "Buku"},
        )
        self.assertEqual(response.status_code, 404)

    def test_kirim_donasi_post_valid(self):
        self.client.force_login(self.donatur)
        response = self.client.post(
            reverse("donasi:kirim_donasi", args=[self.jaket.pk]) + "?nama=Jaket+Kulit&kondisi=terawat&foto=https://example.com/foto.jpg",
            {
                "metode": "antar",
                "tanggal_rencana": besok().isoformat(),
                "jam": "pagi",
                "pesan": "Sudah dicuci",
                "bersih": True,
            },
        )
        self.assertRedirects(response, reverse("donasi:tawaran_saya"))
        p = Penawaran.objects.get()
        self.assertEqual((p.donatur, p.lembaga, p.kebutuhan), (self.donatur, self.lembaga, self.jaket))
        self.assertEqual(p.status, Penawaran.Status.MENUNGGU)

    def test_kirim_donasi_post_invalid(self):
        self.client.force_login(self.donatur)
        response = self.client.post(
            reverse("donasi:kirim_donasi", args=[self.jaket.pk]) + "?nama=Jaket",
            {},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Penawaran.objects.count(), 0)

    def test_tawaran_saya(self):
        self.buat_tawaran(nama_barang="Milik Sekar")
        lain = User.objects.create_user("lain", password="x")
        self.buat_tawaran(donatur=lain, nama_barang="Milik Lain")

        self.client.force_login(self.donatur)
        response = self.client.get(reverse("donasi:tawaran_saya"))
        self.assertContains(response, "Milik Sekar")
        self.assertNotContains(response, "Milik Lain")

        response_filtered = self.client.get(reverse("donasi:tawaran_saya") + "?status=menunggu")
        self.assertContains(response_filtered, "Milik Sekar")

    def test_batalkan_tawaran_standard_dan_htmx(self):
        p1 = self.buat_tawaran()
        self.client.force_login(self.donatur)

        # HTMX delete
        response_htmx = self.client.delete(reverse("donasi:batalkan_tawaran", args=[p1.pk]), **HX_HEADERS)
        self.assertEqual(response_htmx.status_code, 200)
        self.assertFalse(Penawaran.objects.filter(pk=p1.pk).exists())

        # Standard HTTP POST
        p2 = self.buat_tawaran()
        response_http = self.client.post(reverse("donasi:batalkan_tawaran", args=[p2.pk]))
        self.assertRedirects(response_http, reverse("donasi:tawaran_saya"))
        self.assertFalse(Penawaran.objects.filter(pk=p2.pk).exists())

    def test_batalkan_tawaran_orang_lain_atau_diputuskan_404(self):
        p = self.buat_tawaran()
        p.terima()
        self.client.force_login(self.donatur)
        self.assertEqual(
            self.client.delete(reverse("donasi:batalkan_tawaran", args=[p.pk])).status_code, 404
        )

        q = self.buat_tawaran()
        lain = User.objects.create_user("lain", password="x")
        self.client.force_login(lain)
        self.assertEqual(
            self.client.delete(reverse("donasi:batalkan_tawaran", args=[q.pk])).status_code, 404
        )


class SisiLembagaTest(DonasiBaseTestCase):
    def test_dashboard_hanya_untuk_lembaga(self):
        self.client.force_login(self.donatur)
        self.assertEqual(self.client.get(reverse("donasi:dashboard_lembaga")).status_code, 403)

    def test_dashboard_menampilkan_statistik_dan_data_sendiri(self):
        self.buat_tawaran(nama_barang="Tawaran untuk A")
        self.buat_tawaran(
            lembaga=self.lembaga2, kebutuhan=self.sepatu, nama_barang="Tawaran untuk B"
        )
        self.client.force_login(self.lembaga)
        response = self.client.get(reverse("donasi:dashboard_lembaga"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["jumlah_menunggu"], 1)
        self.assertContains(response, "Tawaran untuk A")
        self.assertNotContains(response, "Tawaran untuk B")

    def test_tawaran_masuk_punya_halaman_sendiri_tanpa_menu_navbar(self):
        self.buat_tawaran(nama_barang="Masih Menunggu")
        ditolak = self.buat_tawaran(nama_barang="Sudah Ditolak")
        ditolak.tolak()
        self.buat_tawaran(lembaga=self.lembaga2, kebutuhan=self.sepatu, nama_barang="Tawaran Lain")

        self.lembaga.profile.role = "LEMBAGA"
        self.lembaga.profile.save()
        self.client.force_login(self.lembaga)
        response = self.client.get(reverse("donasi:tawaran_lembaga"))
        self.assertContains(response, "Masih Menunggu")
        self.assertNotContains(response, "Sudah Ditolak")
        self.assertNotContains(response, "Tawaran Lain")
        self.assertNotContains(response, 'aria-current="page">Tawaran masuk')  # tidak ada lagi di navbar

    def test_riwayat_lembaga(self):
        p1 = self.buat_tawaran(nama_barang="Ditolak A")
        p1.tolak()
        self.buat_tawaran(nama_barang="Menunggu B")

        self.client.force_login(self.lembaga)
        response = self.client.get(reverse("donasi:riwayat_lembaga"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ditolak A")
        self.assertNotContains(response, "Menunggu B")

    def test_kebutuhan_list_htmx_dan_filter(self):
        self.client.force_login(self.lembaga)
        response = self.client.get(
            reverse("donasi:kebutuhan_list"), {"q": "jaket", "status": "aktif"}, **HX_HEADERS
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "donasi/_need_rows.html")
        self.assertContains(response, "Jaket anak")

        response_full = self.client.get(reverse("donasi:kebutuhan_list"))
        self.assertEqual(response_full.status_code, 200)

    def test_buat_kebutuhan_tayangkan(self):
        self.client.force_login(self.lembaga)
        response = self.client.post(
            reverse("donasi:kebutuhan_buat"),
            {
                "nama_barang": "Selimut",
                "kategori": Kategori.PERABOT,
                "jumlah": 4,
                "ukuran": [],
                "kondisi_min": Kondisi.TERAWAT,
                "tenggat": besok(7).isoformat(),
                "cerita": "Dingin",
                "aksi": "tayangkan",
            },
        )
        self.assertRedirects(response, reverse("donasi:dashboard_lembaga"))
        k = Kebutuhan.objects.get(nama_barang="Selimut")
        self.assertEqual((k.lembaga, k.status), (self.lembaga, Kebutuhan.Status.AKTIF))

    def test_buat_kebutuhan_simpan_draf(self):
        self.client.force_login(self.lembaga)
        self.client.post(
            reverse("donasi:kebutuhan_buat"),
            {
                "nama_barang": "Selimut Draf",
                "kategori": Kategori.PERABOT,
                "jumlah": 4,
                "kondisi_min": Kondisi.TERAWAT,
                "aksi": "draf",
            },
        )
        k = Kebutuhan.objects.get(nama_barang="Selimut Draf")
        self.assertEqual(k.status, Kebutuhan.Status.DRAFT)

    def test_buat_kebutuhan_terpenuhi_langsung_selesai(self):
        self.client.force_login(self.lembaga)
        self.client.post(
            reverse("donasi:kebutuhan_buat"),
            {
                "nama_barang": "Barang Pas",
                "kategori": Kategori.LAINNYA,
                "jumlah": 2,
                "kondisi_min": Kondisi.TERAWAT,
                "aksi": "tayangkan",
            },
        )
        k = Kebutuhan.objects.get(nama_barang="Barang Pas")
        k.terpenuhi = 2
        k.save()

        self.client.post(
            reverse("donasi:kebutuhan_ubah", args=[k.pk]),
            {
                "nama_barang": "Barang Pas Ubah",
                "kategori": Kategori.LAINNYA,
                "jumlah": 2,
                "kondisi_min": Kondisi.TERAWAT,
                "aksi": "tayangkan",
            },
        )
        k.refresh_from_db()
        self.assertEqual(k.status, Kebutuhan.Status.SELESAI)

    def test_buat_kebutuhan_get_dan_invalid(self):
        self.client.force_login(self.lembaga)
        response_get = self.client.get(reverse("donasi:kebutuhan_buat"))
        self.assertEqual(response_get.status_code, 200)

        response_invalid = self.client.post(
            reverse("donasi:kebutuhan_buat"), {"nama_barang": ""}
        )
        self.assertEqual(response_invalid.status_code, 200)

    def test_ubah_kebutuhan_milik_sendiri(self):
        self.client.force_login(self.lembaga)
        response = self.client.post(
            reverse("donasi:kebutuhan_ubah", args=[self.jaket.pk]),
            {
                "nama_barang": "Jaket Hujan",
                "kategori": Kategori.PAKAIAN_LUARAN,
                "jumlah": 15,
                "ukuran": ["6 th"],
                "kondisi_min": Kondisi.TERAWAT,
                "aksi": "tayangkan",
            },
        )
        self.assertRedirects(response, reverse("donasi:dashboard_lembaga"))
        self.jaket.refresh_from_db()
        self.assertEqual(self.jaket.nama_barang, "Jaket Hujan")

    def test_tidak_bisa_mengubah_atau_menghapus_milik_lembaga_lain(self):
        self.client.force_login(self.lembaga2)
        self.assertEqual(
            self.client.get(reverse("donasi:kebutuhan_ubah", args=[self.jaket.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.delete(reverse("donasi:kebutuhan_hapus", args=[self.jaket.pk])).status_code, 404
        )

    def test_hapus_kebutuhan_standard_dan_htmx(self):
        self.client.force_login(self.lembaga)

        # Hapus via HTMX
        response_htmx = self.client.delete(
            reverse("donasi:kebutuhan_hapus", args=[self.jaket.pk]), **HX_HEADERS
        )
        self.assertEqual(response_htmx.status_code, 200)
        self.assertFalse(Kebutuhan.objects.filter(pk=self.jaket.pk).exists())

        # Hapus via HTTP POST
        k = Kebutuhan.objects.create(lembaga=self.lembaga, nama_barang="Hapus me", jumlah=1)
        response_post = self.client.post(reverse("donasi:kebutuhan_hapus", args=[k.pk]))
        self.assertRedirects(response_post, reverse("donasi:kebutuhan_list"))
        self.assertFalse(Kebutuhan.objects.filter(pk=k.pk).exists())

    def test_kebutuhan_pratinjau(self):
        self.client.force_login(self.lembaga)
        response = self.client.post(
            reverse("donasi:kebutuhan_pratinjau"),
            {
                "nama_barang": "Jaket Hujan",
                "jumlah": "12",
                "ukuran": ["6 th", "8 th"],
                "kondisi_min": "terawat",
                "cerita": "Sangat butuh",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "jaket hujan")

        response_invalid_jumlah = self.client.post(
            reverse("donasi:kebutuhan_pratinjau"),
            {"nama_barang": "Test", "jumlah": "abc"},
        )
        self.assertEqual(response_invalid_jumlah.status_code, 200)

        response_invalid_tenggat = self.client.post(
            reverse("donasi:kebutuhan_pratinjau"),
            {"nama_barang": "Test", "jumlah": "1", "tenggat": "2026-13-45"},
        )
        self.assertEqual(response_invalid_tenggat.status_code, 200)

    def test_aksi_penawaran_terima_tolak_selesai(self):
        self.client.force_login(self.lembaga)

        p1 = self.buat_tawaran()
        r1 = self.client.post(reverse("donasi:penawaran_terima", args=[p1.pk]), **HX_HEADERS)
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, "Menunggu barang")

        r2 = self.client.post(reverse("donasi:penawaran_selesai", args=[p1.pk]), **HX_HEADERS)
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, "stat-menunggu")

        p2 = self.buat_tawaran()
        r3 = self.client.post(reverse("donasi:penawaran_tolak", args=[p2.pk]))
        self.assertRedirects(r3, reverse("donasi:dashboard_lembaga"))
        p2.refresh_from_db()
        self.assertEqual(p2.status, Penawaran.Status.DITOLAK)

    def test_aksi_penawaran_status_sudah_berubah_message(self):
        self.client.force_login(self.lembaga)
        p = self.buat_tawaran()
        p.terima()
        r = self.client.post(reverse("donasi:penawaran_terima", args=[p.pk]))
        self.assertRedirects(r, reverse("donasi:dashboard_lembaga"))

    def test_aksi_penawaran_selesai_kebutuhan_sudah_selesai_oob_delete(self):
        self.client.force_login(self.lembaga)
        p = self.buat_tawaran(jumlah=9)
        p.terima()
        r = self.client.post(reverse("donasi:penawaran_selesai", args=[p.pk]), **HX_HEADERS)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'hx-swap-oob="delete"')

    def test_aksi_penawaran_hanya_post_dan_milik_sendiri(self):
        p = self.buat_tawaran()
        self.client.force_login(self.lembaga)
        self.assertEqual(self.client.get(reverse("donasi:penawaran_terima", args=[p.pk])).status_code, 405)

        self.client.force_login(self.lembaga2)
        self.assertEqual(self.client.post(reverse("donasi:penawaran_terima", args=[p.pk])).status_code, 404)


class JsonTest(DonasiBaseTestCase):
    def test_kebutuhan_json_publik_hanya_yang_aktif(self):
        response = self.client.get(reverse("donasi:kebutuhan_json"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertNotIn("jumlah_tawaran_menunggu", data["results"][0])

    def test_kebutuhan_json_filter_dan_info_login(self):
        self.client.force_login(self.donatur)
        data = self.client.get(
            reverse("donasi:kebutuhan_json"), {"kategori": "alas-kaki", "q": "sepatu"}
        ).json()
        self.assertEqual([k["nama_barang"] for k in data["results"]], ["Sepatu sekolah"])
        self.assertIn("jumlah_tawaran_menunggu", data["results"][0])

    def test_kebutuhan_json_by_id(self):
        self.assertEqual(
            self.client.get(
                reverse("donasi:kebutuhan_json_by_id", args=[self.jaket.pk])
            ).json()["sisa"],
            9,
        )
        self.assertEqual(
            self.client.get(
                reverse("donasi:kebutuhan_json_by_id", args=[self.draf.pk])
            ).status_code,
            404,
        )

    def test_penawaran_json(self):
        self.buat_tawaran()
        self.assertEqual(
            self.client.get(reverse("donasi:penawaran_json")).status_code, 401
        )

        self.client.force_login(self.donatur)
        self.assertEqual(
            self.client.get(reverse("donasi:penawaran_json")).json()["count"], 1
        )

        self.client.force_login(self.lembaga)
        self.assertEqual(
            self.client.get(reverse("donasi:penawaran_json")).json()["count"], 1
        )

        self.client.force_login(self.lembaga2)
        self.assertEqual(
            self.client.get(reverse("donasi:penawaran_json")).json()["count"], 0
        )