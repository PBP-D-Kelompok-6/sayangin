from django.contrib.auth.models import User
from django.db import models


class Product(models.Model):
    CATEGORY_CHOICES = [
        ('atasan', 'Atasan'),
        ('bawahan', 'Bawahan'),
        ('sepatu', 'Sepatu'),
        ('tas', 'Tas'),
        ('aksesori', 'Aksesori'),
        ('buku', 'Buku'),
        ('rumah', 'Rumah & dekor'),
    ]
    CONDITION_CHOICES = [
        ('seperti_baru', 'Seperti baru'),
        ('terawat', 'Bekas, terawat'),
        ('cacat', 'Ada cacat'),
    ]

    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.PositiveIntegerField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    condition_note = models.CharField(max_length=200, blank=True)
    size = models.CharField(max_length=10, blank=True)
    city = models.CharField(max_length=60)
    weight_grams = models.PositiveIntegerField(default=500)
    # Path relatif ke static/, mis. "marketplace/img/blazer-abu.jpg"
    image = models.CharField(max_length=200)
    is_sold = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class CartItem(models.Model):
    # Barang preloved selalu satu-satunya, jadi tidak ada kuantitas.
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')


class Order(models.Model):
    """Satu pesanan = satu penjual, supaya kurir dan pelacakan per penjual."""
    STATUS_CHOICES = [
        ('dibayar', 'Pembayaran diterima'),
        ('dikemas', 'Dikemas penjual'),
        ('dikirim', 'Dalam pengiriman'),
        ('tiba', 'Tiba di alamatmu'),
        ('selesai', 'Selesai'),
    ]
    COURIER_CHOICES = [
        ('reguler', 'Reguler · 2–4 hari'),
        ('kilat', 'Kilat · 1 hari'),
    ]
    # ponytail: ongkir flat per kurir; ganti dengan RajaOngkir kalau API key sudah ada.
    COURIER_COST = {'reguler': 15000, 'kilat': 30000}
    PAYMENT_CHOICES = [
        ('transfer', 'Transfer bank'),
        ('ewallet', 'E-wallet'),
        ('cod', 'Bayar di tempat'),
    ]

    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales')
    recipient = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    city = models.CharField(max_length=60)
    courier = models.CharField(max_length=10, choices=COURIER_CHOICES)
    shipping_cost = models.PositiveIntegerField()
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES)
    tracking_number = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='dibayar')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.code

    @property
    def code(self):
        return f'SYG-{self.pk:05d}'

    @property
    def subtotal(self):
        return sum(item.price for item in self.items.all())

    @property
    def total(self):
        return self.subtotal + self.shipping_cost

    @property
    def status_index(self):
        return [key for key, _ in self.STATUS_CHOICES].index(self.status)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    # Salinan saat dibeli, supaya riwayat tidak berubah kalau produk diedit/dihapus.
    name = models.CharField(max_length=120)
    price = models.PositiveIntegerField()
    image = models.CharField(max_length=200)
