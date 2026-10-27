from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CartItem, Order, Product, WaitItem


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

    def test_empty_search_offers_wait_and_related(self):
        # C2b: "trench coat" tidak ada, tapi sinonim "mantel"/"blazer" tetap menawarkan barang serupa.
        Product.objects.create(seller=self.seller, name='Mantel camel', price=120000, category='atasan',
                               condition='terawat', city='Bandung', image='marketplace/img/mantel-camel.jpg')
        r = self.client.get(reverse('marketplace:catalog'), {'q': 'trench coat krem'})
        self.assertTrue(r.context['nothing_found'])
        self.assertContains(r, 'Tunda beli ini')
        self.assertEqual(r.context['related'][0].name, 'Mantel camel')
        self.assertIn('mantel camel', r.context['other_keywords'])

        self.client.login(username='ira', password='x')
        r = self.client.post(reverse('marketplace:wait_add'), {'keyword': 'trench coat krem', 'days': '14'})
        self.assertRedirects(r, reverse('marketplace:wait_list'))
        item = WaitItem.objects.get()
        self.assertEqual((item.user, item.days), (self.buyer, 14))
        r = self.client.get(reverse('marketplace:wait_list'))
        self.assertContains(r, 'Mantel camel')
        self.client.post(reverse('marketplace:wait_add'), {'keyword': 'x', 'days': '99'})
        self.assertEqual(WaitItem.objects.count(), 1)
