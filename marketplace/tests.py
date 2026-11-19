import tempfile
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from main.models import UserAddress
from . import views
from .models import CartItem, Order, Product
from .ongkir import (
    _destination_id,
    _destination_id_by_postal,
    ongkir,
    ongkir_detail,
    search_destinations,
)


@override_settings(STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
@patch.dict('os.environ', {'RAJAONGKIR_API_KEY': ''})  # tes tidak memanggil RajaOngkir sungguhan
class MarketplaceFlowTest(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        storage = patch.object(views, 'PHOTOS', FileSystemStorage(location=tmp.name, base_url='/marketplace/foto/'))
        storage.start()
        self.addCleanup(storage.stop)
        self.seller = User.objects.create_user('nadia', password='x')
        self.buyer = User.objects.create_user('ira', password='x')
        self.p1 = Product.objects.create(seller=self.seller, name='Blazer wol abu', price=185000, category='atasan',
                                         condition='terawat', size='M', city='Jakarta', image='marketplace/img/blazer-abu.jpg')
        self.p2 = Product.objects.create(seller=self.seller, name='Tas mesh', price=120000, category='tas',
                                         condition='seperti_baru', city='Bandung', image='marketplace/img/tas-mesh.jpg')

    def test_filter_and_search(self):
        r = self.client.get(reverse('marketplace:catalog'), {'kategori': 'atasan'})
        self.assertContains(r, 'Blazer wol abu')
        self.assertNotContains(r, 'Tas mesh')
        r = self.client.get(reverse('marketplace:catalog'), {'q': 'tas', 'maks': '150000'})
        self.assertEqual(list(r.context['products']), [self.p2])
        self.assertEqual(len(r.context['active_filters']), 1)

    def test_cart_checkout_and_tracking(self):
        self.client.login(username='ira', password='x')
        self.client.post(reverse('marketplace:add_to_cart', args=[self.p1.pk]))
        self.client.post(reverse('marketplace:add_to_cart', args=[self.p2.pk]))

        # Langkah 1: alamat wajib lengkap.
        r = self.client.post(reverse('marketplace:checkout_address'), {'recipient': 'Ira'})
        self.assertEqual(r.status_code, 200)
        address = {'recipient': 'Ira', 'phone': '0812', 'address': 'Jl. Margonda', 'city': 'Depok'}
        r = self.client.post(reverse('marketplace:checkout_address'), address)
        self.assertRedirects(r, reverse('marketplace:checkout_shipping'))

        # Langkah 3 belum bisa dibuka sebelum kurir dipilih.
        r = self.client.get(reverse('marketplace:checkout_payment'))
        self.assertRedirects(r, reverse('marketplace:checkout_shipping'))
        r = self.client.post(reverse('marketplace:checkout_shipping'), {})
        self.assertContains(r, 'Pilih kurir untuk penjual ini dulu.')
        r = self.client.post(reverse('marketplace:checkout_shipping'), {f'courier_{self.seller.pk}': 'kilat'})
        self.assertRedirects(r, reverse('marketplace:checkout_payment'))
        self.assertFalse(Order.objects.exists())

        r = self.client.post(reverse('marketplace:checkout_payment'), {'payment': 'transfer'})
        order = Order.objects.get()
        self.assertEqual(order.city, 'Depok')
        self.assertIn('dibayar', order.status_times)
        steps = order.steps()
        self.assertTrue(steps[0]['done'])  # pembayaran langsung tercentang
        self.assertTrue(steps[1]['now'])   # menunggu penjual mengemas
        self.assertRedirects(r, reverse('marketplace:order_detail', args=[order.pk]))
        mine = self.client.get(reverse('marketplace:orders'))
        self.assertEqual(mine.context['bought_count'], 2)
        self.assertEqual(mine.context['order_counts'][0], ('Dibayar', 1))
        self.assertContains(mine, '1 pesanan · 2 barang dibeli')
        self.assertContains(mine, f'<form method="post" action="{reverse("main:logout_user")}">')  # logout wajib POST
        page = self.client.get(reverse('marketplace:order_detail', args=[order.pk]))
        self.assertContains(page, 'Pesanan diterima')
        self.assertContains(page, 'disabled')
        self.assertEqual(order.total, 185000 + 120000 + 30000)
        self.assertFalse(CartItem.objects.exists())
        self.assertFalse(Product.objects.filter(is_sold=False).exists())

        # Pembeli belum bisa konfirmasi sebelum barang tiba; penjual memajukan status.
        url = reverse('marketplace:order_detail', args=[order.pk])
        self.client.post(url, {'action': 'confirm'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'dibayar')
        self.client.login(username='nadia', password='x')
        hub = self.client.get(reverse('marketplace:my_products'))
        self.assertEqual(list(hub.context['to_handle']), [order])  # muncul di "Perlu diproses" penjual
        self.assertContains(hub, 'Jualanku')
        self.assertIn(('Dibayar', 1), hub.context['sale_counts'])
        for _ in range(3):
            self.client.post(url, {'action': 'advance'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'tiba')
        self.assertTrue(order.tracking_number)
        self.client.login(username='ira', password='x')
        self.client.post(url, {'action': 'confirm'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'selesai')

    def test_checkout_uses_saved_profile_addresses_and_links_to_profile(self):
        rumah = UserAddress.objects.create(
            user=self.buyer, label='RUMAH', recipient_name='Ira Arianti', phone_number='081200001111',
            address='Jl. Margonda No. 1', city='Depok', postal_code='16424', is_primary=True,
        )
        kos = UserAddress.objects.create(
            user=self.buyer, label='KOS', recipient_name='Ira Arianti', phone_number='081200001111',
            address='Jl. Cisitu Indah No. 4', district='Coblong', city='Bandung',
            postal_code='40135', rajaongkir_destination_id='17545', is_primary=False,
        )
        apt = UserAddress.objects.create(
            user=self.buyer, label='APARTEMEN', recipient_name='Ira Arianti', phone_number='081200001111',
            address='Apartemen Kalibata City', city='Jakarta Selatan', postal_code='12750', is_primary=False,
        )
        self.client.login(username='ira', password='x')
        self.client.post(reverse('marketplace:add_to_cart', args=[self.p1.pk]))

        # Step 1 menampilkan semua alamat profil, memilih utama secara default, & punya tombol + Tambah alamat ke profil.
        r = self.client.get(reverse('marketplace:checkout_address'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['selected_address_id'], rumah.pk)
        self.assertContains(r, 'Rumah')
        self.assertContains(r, 'Kos')
        self.assertContains(r, 'Apartemen')
        self.assertContains(r, '+ Tambah alamat')
        self.assertContains(r, f'{reverse("main:show_profile")}?add_address=1&amp;next={reverse("marketplace:checkout_address")}')

        # Kembali dari profil dengan ?address_id memilih alamat baru/tertentu secara otomatis.
        r_sel = self.client.get(reverse('marketplace:checkout_address'), {'address_id': apt.pk})
        self.assertEqual(r_sel.context['selected_address_id'], apt.pk)

        # Pilih Kos langsung lanjut ke pengiriman tanpa mengetik alamat lagi.
        r_post = self.client.post(reverse('marketplace:checkout_address'), {'selected_address_id': kos.pk})
        self.assertRedirects(r_post, reverse('marketplace:checkout_shipping'))
        ship = self.client.get(reverse('marketplace:checkout_shipping'))
        self.assertContains(ship, 'Kos · Bandung 40135')

        self.client.post(reverse('marketplace:checkout_shipping'), {f'courier_{self.seller.pk}': 'reguler'})
        self.client.post(reverse('marketplace:checkout_payment'), {'payment': 'transfer'})
        order = Order.objects.get()
        self.assertEqual(order.city, 'Bandung')
        self.assertEqual(order.postal_code, '40135')
        self.assertEqual(order.address_label, 'Kos')
        self.assertEqual(order.recipient, 'Ira Arianti')

    def test_checkout_saved_address_missing_phone_prompts_and_saves_back(self):
        addr = UserAddress.objects.create(
            user=self.buyer, label='KANTOR', recipient_name='Ira Arianti', phone_number='',
            address='Jl. Sudirman Kav. 52', city='Jakarta Selatan', postal_code='12190', is_primary=True,
        )
        self.client.login(username='ira', password='x')
        self.client.post(reverse('marketplace:add_to_cart', args=[self.p1.pk]))

        r_err = self.client.post(reverse('marketplace:checkout_address'), {'selected_address_id': addr.pk})
        self.assertEqual(r_err.status_code, 200)
        self.assertIn('phone_fallback', r_err.context['errors'])

        r_ok = self.client.post(reverse('marketplace:checkout_address'), {
            'selected_address_id': addr.pk, 'phone_fallback': '08123456789',
        })
        self.assertRedirects(r_ok, reverse('marketplace:checkout_shipping'))
        addr.refresh_from_db()
        self.assertEqual(addr.phone_number, '08123456789')
        self.buyer.profile.refresh_from_db()
        self.assertEqual(self.buyer.profile.phone_number, '08123456789')

    def test_checkout_manual_address_saves_into_user_profile(self):
        self.client.login(username='ira', password='x')
        self.client.post(reverse('marketplace:add_to_cart', args=[self.p1.pk]))

        r = self.client.post(reverse('marketplace:checkout_address'), {
            'label': 'APARTEMEN', 'recipient': 'Ira', 'phone': '08129999',
            'address': 'Jl. Jenderal Sudirman No. 88', 'city': 'Balikpapan', 'postal_code': '76111',
        })
        self.assertRedirects(r, reverse('marketplace:checkout_shipping'))
        saved = UserAddress.objects.get(user=self.buyer)
        self.assertEqual(saved.label, 'APARTEMEN')
        self.assertEqual(saved.city, 'Balikpapan')
        self.assertEqual(saved.rajaongkir_city_id, '19')
        self.assertEqual(saved.province, 'Kalimantan Timur')
        self.assertTrue(saved.is_primary)

    def test_cannot_buy_own_product(self):
        self.client.login(username='nadia', password='x')
        self.client.post(reverse('marketplace:add_to_cart', args=[self.p1.pk]))
        self.assertFalse(CartItem.objects.exists())

    def test_empty_search_suggests_related(self):
        # C2b: "trench coat" tidak ada, tapi sinonim "mantel" tetap menawarkan barang serupa.
        Product.objects.create(seller=self.seller, name='Mantel camel', price=120000, category='atasan',
                               condition='terawat', city='Bandung', image='marketplace/img/mantel-camel.jpg')
        r = self.client.get(reverse('marketplace:catalog'), {'q': 'trench coat krem'})
        self.assertTrue(r.context['nothing_found'])
        self.assertContains(r, 'Belum ada versi')
        self.assertEqual(r.context['related'][0].name, 'Mantel camel')
        self.assertIn('mantel camel', r.context['other_keywords'])

    # ---------- CRUD barang oleh penjual ----------

    @staticmethod
    def photo(name='flanel.gif'):
        gif = b'GIF89a\x01\x00\x01\x00\x00\x00\x00;'
        return SimpleUploadedFile(name, gif, content_type='image/gif')

    def product_data(self, photos=None, **extra):
        data = {'name': 'Kemeja flanel', 'price': '40000', 'category': 'atasan', 'condition': 'terawat',
                'condition_note': '', 'size': 'L', 'city': 'Depok', 'weight_grams': '400', 'action': 'publish',
                'photos': [self.photo()] if photos is None else photos}
        data.update(extra)
        return data

    def test_seller_can_create_edit_delete_product(self):
        self.client.login(username='ira', password='x')
        r = self.client.post(reverse('marketplace:product_create'),
                             self.product_data(photos=[self.photo('a.jpe'), self.photo('b.png')]))
        product = Product.objects.get(name='Kemeja flanel')
        self.assertRedirects(r, reverse('marketplace:product_published', args=[product.pk]))
        self.assertContains(self.client.get(r.url), 'sudah <em>masuk Marketplace</em>')
        self.assertEqual(product.seller, self.buyer)
        self.assertTrue(product.photo.startswith('/marketplace/foto/'))
        self.assertTrue(product.photo.endswith('.jpg'))  # .jpe disimpan sebagai .jpg
        self.assertEqual(len(product.photos), 2)  # foto utama + 1 foto tambahan
        served = self.client.get(product.photo)
        self.assertEqual(served.status_code, 200)  # foto upload bisa dibuka
        served.close()
        self.assertContains(self.client.get(reverse('marketplace:my_products')), 'Kemeja flanel')

        # Edit tanpa foto baru: foto lama tetap dipakai.
        self.client.post(reverse('marketplace:product_edit', args=[product.pk]), self.product_data(photos=[], price='35000'))
        product.refresh_from_db()
        self.assertEqual((product.price, len(product.photos)), (35000, 2))

        r = self.client.post(reverse('marketplace:product_delete', args=[product.pk]))
        self.assertRedirects(r, reverse('marketplace:my_products'))
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_product_form_validation(self):
        self.client.login(username='ira', password='x')
        r = self.client.post(reverse('marketplace:product_create'), self.product_data(price='500', condition=''))
        self.assertContains(r, 'Isi harga, minimal Rp1.000.')
        self.assertContains(r, '2 kolom perlu diperbaiki')  # banner error seperti di Figma
        r = self.client.post(reverse('marketplace:product_create'), self.product_data(condition='cacat'))
        self.assertContains(r, 'Jelaskan cacatnya')
        r = self.client.post(reverse('marketplace:product_create'), self.product_data(photos=[]))
        self.assertContains(r, 'Tambahkan minimal 1 foto')
        fake = SimpleUploadedFile('x.html', b'<script>alert(1)</script>', content_type='image/gif')
        r = self.client.post(reverse('marketplace:product_create'), self.product_data(photos=[fake]))
        self.assertContains(r, 'bukan file gambar')  # file selain gambar ditolak
        r = self.client.post(reverse('marketplace:product_create'), self.product_data(photos=[self.photo() for _ in range(5)]))
        self.assertContains(r, 'Maksimal 4 foto')
        self.assertFalse(Product.objects.filter(name='Kemeja flanel').exists())

    def test_draft_is_hidden_until_published(self):
        self.client.login(username='ira', password='x')
        self.client.post(reverse('marketplace:product_create'), self.product_data(action='draft'))
        draft = Product.objects.get(name='Kemeja flanel')
        self.assertTrue(draft.is_draft)
        self.assertNotIn(draft, self.client.get(reverse('marketplace:catalog')).context['products'])
        self.assertEqual(self.client.get(reverse('marketplace:products_api'), {'q': 'flanel'}).json()['count'], 0)
        self.assertContains(self.client.get(reverse('marketplace:my_products')), 'Draf <em>tersimpan</em>')
        self.client.login(username='nadia', password='x')
        self.assertEqual(self.client.get(reverse('marketplace:detail', args=[draft.pk])).status_code, 404)
        self.client.login(username='ira', password='x')
        r = self.client.post(reverse('marketplace:product_edit', args=[draft.pk]), self.product_data(photos=[]))
        self.assertRedirects(r, reverse('marketplace:product_published', args=[draft.pk]))
        self.assertIn(draft, self.client.get(reverse('marketplace:catalog')).context['products'])

    def test_only_owner_can_edit_or_delete(self):
        self.client.login(username='ira', password='x')  # p1 milik nadia
        self.assertEqual(self.client.get(reverse('marketplace:product_edit', args=[self.p1.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('marketplace:product_delete', args=[self.p1.pk])).status_code, 404)
        self.assertTrue(Product.objects.filter(pk=self.p1.pk).exists())
        # Barang yang sudah terjual tidak bisa dihapus, bahkan oleh pemiliknya.
        Product.objects.filter(pk=self.p1.pk).update(is_sold=True)
        self.client.login(username='nadia', password='x')
        self.assertEqual(self.client.post(reverse('marketplace:product_delete', args=[self.p1.pk])).status_code, 404)

    # ---------- AJAX + JSON ----------

    def test_ajax_cart_returns_json(self):
        self.client.login(username='ira', password='x')
        ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        r = self.client.post(reverse('marketplace:add_to_cart', args=[self.p1.pk]), **ajax)
        self.assertEqual(r.json(), {'ok': True, 'message': 'Blazer wol abu masuk keranjang.', 'cart_count': 1})
        r = self.client.post(reverse('marketplace:add_to_cart', args=[self.p2.pk]), **ajax)
        self.assertEqual(r.json()['cart_count'], 2)
        r = self.client.post(reverse('marketplace:remove_from_cart', args=[self.p1.pk]), **ajax)
        self.assertEqual(r.json(), {'ok': True, 'cart_count': 1, 'subtotal': 'Rp120.000', 'empty': False})
        # Barang sendiri ditolak dengan JSON juga.
        self.client.login(username='nadia', password='x')
        r = self.client.post(reverse('marketplace:add_to_cart', args=[self.p1.pk]), **ajax)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['ok'])

    def test_products_api_json(self):
        r = self.client.get(reverse('marketplace:products_api'), {'kategori': 'tas'})
        data = r.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['name'], 'Tas mesh')
        self.assertEqual(data['results'][0]['price_label'], 'Rp120.000')
        self.assertEqual(self.client.get(reverse('marketplace:products_api'), {'id': self.p1.pk}).json()['results'][0]['size'], 'M')
        self.assertEqual(self.client.get(reverse('marketplace:products_api'), {'q': 'blazer'}).json()['count'], 1)
        r = self.client.get(reverse('marketplace:products_api'), {'id': [self.p1.pk, 'x'], 'limit': '5'})
        self.assertEqual([p['name'] for p in r.json()['results']], ['Blazer wol abu'])
        self.assertEqual(self.client.get(reverse('marketplace:products_api'), {'limit': '1'}).json()['count'], 1)


class CartCountApiTest(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user('nadia', password='x')
        self.buyer = User.objects.create_user('ira', password='x')
        self.product = Product.objects.create(seller=self.seller, name='Blazer wol abu', price=185000,
                                              category='Atasan', condition='terawat', size='M')

    def test_jumlah_keranjang_terbaru_setelah_menambah_barang(self):
        self.client.force_login(self.buyer)
        url = reverse('marketplace:cart_count_api')
        self.assertEqual(self.client.get(url).json(), {'cart_count': 0})
        self.client.post(reverse('marketplace:add_to_cart', args=[self.product.pk]))
        self.assertEqual(self.client.get(url).json(), {'cart_count': 1})

    def test_tamu_tidak_bisa_melihat_jumlah_keranjang(self):
        self.assertEqual(self.client.get(reverse('marketplace:cart_count_api')).status_code, 302)


class PilihanBersamaTest(TestCase):
    def test_lemari_marketplace_donasi_memakai_pilihan_yang_sama(self):
        from donasi.models import Kategori, Kondisi
        from lemari.models import WardrobeItem
        from sayangin.pilihan import KATEGORI, KONDISI

        self.assertEqual(Product.CATEGORY_CHOICES, KATEGORI)
        self.assertEqual(Product.CONDITION_CHOICES, KONDISI)
        self.assertEqual(list(Kategori.choices), KATEGORI)
        self.assertEqual(list(Kondisi.choices), KONDISI)
        self.assertEqual(list(WardrobeItem._meta.get_field('category').choices), KATEGORI)


class OngkirTest(TestCase):
    def setUp(self):
        _destination_id.cache_clear()
        _destination_id_by_postal.cache_clear()

    @patch.dict('os.environ', {'RAJAONGKIR_API_KEY': ''})
    def test_without_key_uses_flat_rate(self):
        self.assertEqual(ongkir('Jakarta', 'Depok', 500), Order.COURIER_COST)

    @patch.dict('os.environ', {'RAJAONGKIR_API_KEY': 'k'})
    @patch('marketplace.ongkir.requests')
    def test_with_key_uses_api_and_falls_back_per_courier(self, req):
        req.RequestException = Exception
        req.get.return_value = Mock(json=lambda: {'data': [{'id': 6, 'city_name': 'CIREBON'}, {'id': 7, 'city_name': 'DEPOK'}]})
        req.post.return_value = Mock(json=lambda: {'data': [{'service': 'REG', 'cost': 11000}]})
        self.assertEqual(ongkir('Jakarta', 'Depok', 500), {'reguler': 11000, 'kilat': Order.COURIER_COST['kilat']})
        self.assertEqual(req.post.call_args.kwargs['data']['destination'], 7)
        req.post.side_effect = Exception('down')
        self.assertEqual(ongkir('Jakarta', 'Depok', 500), Order.COURIER_COST)

    @patch.dict('os.environ', {'RAJAONGKIR_API_KEY': 'k'})
    @patch('marketplace.ongkir.requests')
    def test_ongkir_detail_uses_saved_destination_id_and_postal_code_and_ctc(self, req):
        req.RequestException = Exception
        req.post.return_value = Mock(json=lambda: {
            'data': [
                {'service': 'CTC', 'cost': 9000, 'etd': '1-2 day'},
                {'service': 'CTCYES', 'cost': 18000, 'etd': '1 day'},
            ]
        })
        res = ongkir_detail('Depok', 'Jakarta Selatan', 600, origin_id='101', dest_id='202')
        self.assertEqual(res['source'], 'rajaongkir')
        self.assertEqual(res['costs'], {'reguler': 9000, 'kilat': 18000})
        self.assertIn('JNE CTC', res['labels']['reguler'])
        self.assertIn('1–2 hari', res['labels']['reguler'])
        # Karena origin_id & dest_id sudah ada, tidak perlu GET destination.
        req.get.assert_not_called()
        self.assertEqual(req.post.call_args.kwargs['data']['origin'], 101)
        self.assertEqual(req.post.call_args.kwargs['data']['destination'], 202)

        # Tanpa dest_id tapi dengan kode pos 5 digit -> cari berdasarkan kode pos.
        req.get.return_value = Mock(json=lambda: {
            'data': [{'id': 555, 'city_name': 'DEPOK', 'zip_code': '16424'}]
        })
        ongkir_detail('Depok', 'Depok', 500, origin_id='101', dest_postal_code='16424')
        self.assertEqual(req.get.call_args.kwargs['params']['search'], '16424')
        self.assertEqual(req.post.call_args.kwargs['data']['destination'], 555)

    @patch.dict('os.environ', {'RAJAONGKIR_API_KEY': ''})
    def test_search_destinations_local_fallback_supports_expanded_cities_and_postcodes(self):
        res_city = search_destinations('Balikpapan')
        self.assertEqual(res_city['source'], 'local')
        self.assertEqual(res_city['results'][0]['city'], 'Balikpapan')
        self.assertEqual(res_city['results'][0]['province'], 'Kalimantan Timur')
        self.assertEqual(res_city['results'][0]['postal_code'], '76111')

        res_alias = search_destinations('Solo')
        self.assertEqual(res_alias['results'][0]['city'], 'Surakarta')

        res_zip = search_destinations('99111')
        self.assertEqual(res_zip['results'][0]['city'], 'Jayapura')

    @patch.dict('os.environ', {'RAJAONGKIR_API_KEY': 'k'})
    @patch('marketplace.ongkir.requests')
    def test_search_destinations_live_rajaongkir(self, req):
        req.RequestException = Exception
        req.get.return_value = Mock(json=lambda: {
            'data': [{
                'id': 17545,
                'province_name': 'JAWA BARAT',
                'city_name': 'DEPOK',
                'district_name': 'BEJI',
                'subdistrict_name': 'PONDOK CINA',
                'zip_code': '16424',
            }]
        })
        res = search_destinations('16424')
        self.assertEqual(res['source'], 'rajaongkir')
        item = res['results'][0]
        self.assertEqual(item['destination_id'], '17545')
        self.assertEqual(item['city'], 'Depok')
        self.assertEqual(item['district'], 'Beji')
        self.assertEqual(item['subdistrict'], 'Pondok Cina')
        self.assertEqual(item['postal_code'], '16424')
        self.assertEqual(item['rajaongkir_city_id'], '115')

@override_settings(STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class MarketplaceApiTest(TestCase):
    """API DRF untuk Flutter: /marketplace/api/..."""

    def setUp(self):
        self.seller = User.objects.create_user('nadia', password='x')
        self.buyer = User.objects.create_user('ira', password='x')
        self.p1 = Product.objects.create(seller=self.seller, name='Blazer wol abu', price=185000, category='atasan',
                                         condition='terawat', size='M', city='Jakarta', image='marketplace/img/blazer-abu.jpg')
        self.p2 = Product.objects.create(seller=self.seller, name='Tas mesh', price=120000, category='tas',
                                         condition='seperti_baru', city='Bandung', image='marketplace/img/tas-mesh.jpg')
        self.draft = Product.objects.create(seller=self.seller, name='Draf', price=1, category='tas', condition='terawat',
                                            city='Bandung', image='x.jpg', is_draft=True)

    def test_catalog_is_public_and_uses_web_filters(self):
        data = self.client.get(reverse('marketplace:api_catalog'), {'kategori': 'tas'}).json()
        self.assertEqual([p['name'] for p in data['results']], ['Tas mesh'])  # draf tidak ikut
        self.assertTrue(data['results'][0]['photo'].startswith('http://'))
        self.assertEqual(self.client.get(reverse('marketplace:api_product', args=[self.p1.pk])).json()['in_cart'], False)
        self.assertEqual(self.client.get(reverse('marketplace:api_product', args=[self.draft.pk])).status_code, 404)

    def test_cart_needs_login(self):
        self.assertEqual(self.client.get(reverse('marketplace:api_cart')).status_code, 403)

    def test_lembaga_cannot_use_cart_or_orders(self):
        lembaga = User.objects.create_user('panti', password='x')
        lembaga.profile.role = 'LEMBAGA'
        lembaga.profile.save()
        self.client.login(username='panti', password='x')
        self.assertEqual(self.client.get(reverse('marketplace:api_cart')).status_code, 403)
        self.assertEqual(self.client.get(reverse('marketplace:api_orders')).status_code, 403)
        self.assertEqual(self.client.get(reverse('marketplace:api_catalog')).status_code, 200)  # katalog tetap terbuka

    def test_cart_add_and_remove(self):
        self.client.login(username='ira', password='x')
        r = self.client.post(reverse('marketplace:api_cart'), {'product': self.p1.pk}, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.json()['count'], r.json()['subtotal']), (1, 185000))
        r = self.client.delete(reverse('marketplace:api_cart_item', args=[self.p1.pk]))
        self.assertEqual(r.json()['count'], 0)

    def test_cannot_buy_own_product(self):
        self.client.login(username='nadia', password='x')
        r = self.client.post(reverse('marketplace:api_cart'), {'product': self.p1.pk}, content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_orders_only_for_buyer_or_seller(self):
        order = Order(buyer=self.buyer, seller=self.seller, recipient='Ira', phone='08', address='Jl', city='Depok',
                      courier='reguler', shipping_cost=15000, payment_method='transfer')
        order.set_status('dibayar')
        order.save()
        order.items.create(product=self.p1, name=self.p1.name, price=self.p1.price, image=self.p1.image)
        self.client.login(username='ira', password='x')
        rows = self.client.get(reverse('marketplace:api_orders')).json()
        self.assertEqual((rows[0]['code'], rows[0]['total']), (order.code, 200000))
        detail = self.client.get(reverse('marketplace:api_order', args=[order.pk])).json()
        self.assertEqual(len(detail['steps']), 5)
        User.objects.create_user('lain', password='x')
        self.client.login(username='lain', password='x')
        self.assertEqual(self.client.get(reverse('marketplace:api_order', args=[order.pk])).status_code, 404)

class SeedMarketplaceTest(TestCase):
    """python manage.py seed_marketplace: ~100 barang contoh, semua fotonya ada, aman dijalankan ulang."""

    def test_seed_creates_100_valid_products_once(self):
        from io import StringIO
        from pathlib import Path

        from django.conf import settings
        from django.core.management import call_command

        call_command('seed_marketplace', stdout=StringIO())
        self.assertEqual(Product.objects.count(), 100)
        categories = dict(Product.CATEGORY_CHOICES)
        conditions = dict(Product.CONDITION_CHOICES)
        for p in Product.objects.all():
            self.assertIn(p.category, categories, p.name)
            self.assertIn(p.condition, conditions, p.name)
            self.assertTrue((Path(settings.BASE_DIR) / 'marketplace' / 'static' / p.image).is_file(), p.image)
        self.assertEqual(set(Product.objects.values_list('category', flat=True)), set(categories))

        call_command('seed_marketplace', stdout=StringIO())  # dijalankan ulang tidak dobel
        self.assertEqual(Product.objects.count(), 100)
