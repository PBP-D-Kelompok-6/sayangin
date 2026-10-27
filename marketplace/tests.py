from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CartItem, Order, Product


@override_settings(STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class MarketplaceFlowTest(TestCase):
    def setUp(self):
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
        for _ in range(3):
            self.client.post(url, {'action': 'advance'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'tiba')
        self.assertTrue(order.tracking_number)
        self.client.login(username='ira', password='x')
        self.client.post(url, {'action': 'confirm'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'selesai')

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

    def product_data(self, **extra):
        data = {'name': 'Kemeja flanel', 'price': '40000', 'category': 'atasan', 'condition': 'terawat',
                'condition_note': '', 'size': 'L', 'city': 'Depok', 'weight_grams': '400',
                'used_duration': '1 tahun', 'description': 'Masih tebal.', 'image': 'https://example.com/flanel.jpg'}
        data.update(extra)
        return data

    def test_seller_can_create_edit_delete_product(self):
        self.client.login(username='ira', password='x')
        r = self.client.post(reverse('marketplace:product_create'), self.product_data())
        product = Product.objects.get(name='Kemeja flanel')
        self.assertRedirects(r, reverse('marketplace:detail', args=[product.pk]))
        self.assertEqual(product.seller, self.buyer)
        self.assertEqual(product.photo, 'https://example.com/flanel.jpg')
        self.assertContains(self.client.get(reverse('marketplace:my_products')), 'Kemeja flanel')

        self.client.post(reverse('marketplace:product_edit', args=[product.pk]), self.product_data(price='35000'))
        product.refresh_from_db()
        self.assertEqual(product.price, 35000)

        r = self.client.post(reverse('marketplace:product_delete', args=[product.pk]))
        self.assertRedirects(r, reverse('marketplace:my_products'))
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_product_form_validation(self):
        self.client.login(username='ira', password='x')
        r = self.client.post(reverse('marketplace:product_create'), self.product_data(price='500'))
        self.assertContains(r, 'Harga minimal Rp1.000.')
        r = self.client.post(reverse('marketplace:product_create'), self.product_data(condition='cacat'))
        self.assertContains(r, 'Jelaskan cacatnya')
        self.assertFalse(Product.objects.filter(name='Kemeja flanel').exists())

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
        self.assertEqual(self.client.get(reverse('marketplace:products_api'), {'q': 'blazer'}).json()['count'], 1)
