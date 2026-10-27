from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.db import models
from django.templatetags.static import static
from django.utils import timezone

WIB = ZoneInfo('Asia/Jakarta')
BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
BULAN_PANJANG = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September',
                 'Oktober', 'November', 'Desember']


def photo_url(image):
    """Link foto penjual dipakai apa adanya; path data contoh diubah jadi URL static."""
    return image if image.startswith(('http://', 'https://')) else static(image)


def tanggal(dt, with_time=True):
    """'25 Okt, 10.12' dalam WIB (settings proyek masih UTC)."""
    dt = dt.astimezone(WIB)
    text = f'{dt.day} {BULAN[dt.month - 1]}'
    return f'{text}, {dt:%H.%M}' if with_time else text


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
    used_duration = models.CharField(max_length=30, blank=True)  # mis. "2 tahun"
    # Foto: link http(s) dari penjual, atau path static untuk data contoh ("marketplace/img/blazer-abu.jpg").
    # ponytail: link foto, bukan upload file (upload butuh Pillow + penyimpanan media di server).
    image = models.CharField(max_length=500)
    is_sold = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def photo(self):
        return photo_url(self.image)


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
        ('selesai', 'Selesai & ulas'),
    ]
    STATUS_SHORT = {'dibayar': 'Dibayar', 'dikemas': 'Dikemas', 'dikirim': 'Dikirim', 'tiba': 'Tiba', 'selesai': 'Selesai'}
    STATUS_TITLE = {
        'dibayar': ('Pembayaran', 'diterima'), 'dikemas': ('Pesanan sedang', 'dikemas'),
        'dikirim': ('Pesanan sedang', 'dikirim'), 'tiba': ('Pesanan sudah', 'tiba'), 'selesai': ('Pesanan', 'selesai'),
    }
    COURIER_DAYS = {'reguler': (2, 4), 'kilat': (1, 1)}
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
    status_times = models.JSONField(default=dict)  # {status: ISO waktu dicapai}
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

    @property
    def status_short(self):
        return self.STATUS_SHORT[self.status]

    def set_status(self, status):
        self.status = status
        self.status_times[status] = timezone.now().isoformat()

    @property
    def eta(self):
        low, high = self.COURIER_DAYS[self.courier]
        start = self.created_at + timedelta(days=low)
        end = self.created_at + timedelta(days=high)
        if low == high:
            return tanggal(start, with_time=False)
        if start.month == end.month:
            return f'{start.astimezone(WIB).day}–{tanggal(end, with_time=False)}'
        return f'{tanggal(start, with_time=False)} – {tanggal(end, with_time=False)}'

    def steps(self):
        todo_meta = {'dikemas': 'Menunggu penjual mengemas', 'tiba': f'Perkiraan {self.eta}',
                     'selesai': 'Konfirmasi lalu beri ulasan'}
        # Pembayaran langsung selesai, jadi yang "sedang berjalan" adalah langkah sesudahnya.
        now = self.status_index + (1 if self.status == 'dibayar' else 0)
        result = []
        for i, (key, label) in enumerate(self.STATUS_CHOICES):
            reached = self.status_times.get(key)
            if i <= self.status_index and reached:
                meta = tanggal(datetime.fromisoformat(reached))
                if key == 'dikirim' and self.tracking_number:
                    meta = f'Bersama JNE · {meta}'
            else:
                meta = todo_meta.get(key, '')
            result.append({'label': label, 'meta': meta,
                           'done': i < now or self.status == 'selesai',
                           'now': i == now and self.status != 'selesai'})
        return result


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    # Salinan saat dibeli, supaya riwayat tidak berubah kalau produk diedit/dihapus.
    name = models.CharField(max_length=120)
    price = models.PositiveIntegerField()
    image = models.CharField(max_length=500)

    @property
    def photo(self):
        return photo_url(self.image)
