from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.client import BOUNDARY, encode_multipart
from django.urls import reverse

from .models import SaleListing, WardrobeItem


class LemariFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="password123")
        self.other_user = User.objects.create_user(username="bob", password="password123")
        self.photo = SimpleUploadedFile("shirt.jpg", b"fake-image-content", content_type="image/jpeg")

    def login(self):
        self.client.force_login(self.user)

    def valid_item_data(self, **overrides):
        data = {"nama": "Kemeja linen", "kategori": "Pakaian", "ukuran": "M", "terakhir_dipakai": "3–6 bulan lalu", "warna": "Putih", "kapan_dibeli": "2025-08", "catatan": "Kancing masih lengkap", "action": "save"}
        data.update(overrides)
        return data

    def valid_listing_data(self, **overrides):
        data = {"judul": "Kemeja linen untuk dijual", "kategori": "Pakaian", "ukuran": "M", "kondisi": "terawat", "catatan": "Kondisi baik", "harga": "120000", "berat": "800", "dikirim_dari": "Depok"}
        data.update(overrides)
        return data

    def post_multipart(self, url, data):
        return self.client.post(url, encode_multipart(BOUNDARY, data), content_type=f"multipart/form-data; boundary={BOUNDARY}")

    def test_index_only_shows_items_owned_by_logged_in_user(self):
        own_item = WardrobeItem.objects.create(owner=self.user, name="Punya Alice", category="Pakaian", last_used="3–6 bulan lalu")
        WardrobeItem.objects.create(owner=self.other_user, name="Punya Bob", category="Pakaian", last_used="3–6 bulan lalu")
        self.login()
        response = self.client.get(reverse("lemari:index"))
        self.assertContains(response, own_item.name)
        self.assertNotContains(response, "Punya Bob")

    def test_empty_wardrobe_uses_empty_page(self):
        self.login()
        response = self.client.get(reverse("lemari:index"))
        self.assertTemplateUsed(response, "lemari/kosong.html")
        self.assertContains(response, "Tambah barang pertama")

    def test_add_item_assigns_current_user(self):
        self.login()
        data = self.valid_item_data()
        data["foto"] = self.photo
        response = self.post_multipart(reverse("lemari:tambah_barang"), data)
        self.assertRedirects(response, reverse("lemari:index"))
        item = WardrobeItem.objects.get(name="Kemeja linen")
        self.assertEqual(item.owner, self.user)
        self.assertEqual(item.size, "M")
        self.assertEqual(item.purchased_at, "2025-08")

    def test_save_and_add_again_stays_on_add_page(self):
        self.login()
        data = self.valid_item_data(action="save_add")
        data["foto"] = self.photo
        response = self.post_multipart(reverse("lemari:tambah_barang"), data)
        self.assertRedirects(response, reverse("lemari:tambah_barang"))
        self.assertEqual(WardrobeItem.objects.filter(owner=self.user).count(), 1)

    def test_user_cannot_open_another_users_detail(self):
        item = WardrobeItem.objects.create(owner=self.other_user, name="Rahasia Bob", category="Aksesori", last_used="Lupa")
        self.login()
        response = self.client.get(reverse("lemari:detail_barang", args=[item.pk]))
        self.assertEqual(response.status_code, 404)

    def test_reminder_toggle_can_turn_off_and_on(self):
        item = WardrobeItem.objects.create(owner=self.user, name="Barang pengingat", category="Pakaian", last_used="Lebih dari 6 bulan")
        self.login()
        self.client.post(reverse("lemari:toggle_reminder", args=[item.pk]))
        item.refresh_from_db()
        self.assertFalse(item.reminder_enabled)
        self.client.post(reverse("lemari:toggle_reminder", args=[item.pk]))
        item.refresh_from_db()
        self.assertTrue(item.reminder_enabled)

    def test_sell_page_prefills_source_wardrobe_item(self):
        item = WardrobeItem.objects.create(owner=self.user, name="Jaket hijau", category="Pakaian", last_used="3–6 bulan lalu")
        self.login()
        response = self.client.get(reverse("lemari:jual") + f"?item={item.pk}")
        self.assertContains(response, "Jaket hijau")
        self.assertContains(response, f'name="source_item" value="{item.pk}"')

    def test_publishing_listing_keeps_source_item_and_owner(self):
        item = WardrobeItem.objects.create(owner=self.user, name="Jaket hijau", category="Pakaian", last_used="3–6 bulan lalu")
        self.login()
        response = self.client.post(reverse("lemari:jual") + f"?item={item.pk}", self.valid_listing_data(source_item=str(item.pk)))
        listing = SaleListing.objects.get(title="Kemeja linen untuk dijual")
        self.assertEqual(listing.owner, self.user)
        self.assertEqual(listing.source_item, item)
        self.assertRedirects(response, reverse("lemari:jual_sukses", args=[listing.pk]))
