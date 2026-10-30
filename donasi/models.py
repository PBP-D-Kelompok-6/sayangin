import datetime

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone


class Kategori(models.TextChoices):
    PAKAIAN_LUARAN = "pakaian-luaran", "Pakaian · Luaran"
    PAKAIAN_ATASAN = "pakaian-atasan", "Pakaian · Atasan"
    PAKAIAN_BAWAHAN = "pakaian-bawahan", "Pakaian · Bawahan"
    ALAS_KAKI = "alas-kaki", "Alas kaki"
    BUKU = "buku", "Buku"
    PERLENGKAPAN_SEKOLAH = "perlengkapan-sekolah", "Perlengkapan sekolah"
    PERABOT = "perabot", "Perabot"
    MAINAN = "mainan", "Mainan"
    LAINNYA = "lainnya", "Lainnya"


class Kondisi(models.TextChoices):
    SEPERTI_BARU = "seperti-baru", "Seperti baru"
    TERAWAT = "terawat", "Bekas, terawat"
    ADA_CACAT = "ada-cacat", "Ada cacat kecil"


RANK_KONDISI = {
    Kondisi.SEPERTI_BARU: 3,
    Kondisi.TERAWAT: 2,
    Kondisi.ADA_CACAT: 1,
}

# Lembaga hanya boleh meminta "seperti baru" atau "bekas, terawat".
KONDISI_MIN_CHOICES = Kondisi.choices[:2]

UKURAN_CHOICES = [(u, u) for u in ("6 th", "8 th", "10 th", "12 th", "S", "M", "L", "XL")]


def _kondisi_yang_memenuhi(kondisi_barang):
    """Nilai kondisi_min yang masih dipenuhi oleh barang dengan kondisi tertentu."""
    rank_barang = RANK_KONDISI.get(kondisi_barang, 0)
    return [nilai for nilai, _ in KONDISI_MIN_CHOICES if RANK_KONDISI[nilai] <= rank_barang]


class KebutuhanQuerySet(models.QuerySet):
    def aktif(self):
        """Kebutuhan yang tayang, belum lewat tenggat, dan belum terpenuhi."""
        hari_ini = timezone.localdate()
        return (
            self.filter(status=Kebutuhan.Status.AKTIF, terpenuhi__lt=F("jumlah"))
            .filter(Q(tenggat__isnull=True) | Q(tenggat__gte=hari_ini))
        )

    def cocok_dengan(self, kategori="", ukuran="", kondisi=""):
        """Kebutuhan aktif yang cocok dengan barang dari Lemari Digital."""
        qs = self.aktif().select_related("lembaga")
        if kategori:
            qs = qs.filter(kategori=kategori)
        if kondisi:
            qs = qs.filter(kondisi_min__in=_kondisi_yang_memenuhi(kondisi))
        hasil = list(qs)
        if ukuran:
            hasil = [k for k in hasil if not k.ukuran_list or ukuran in k.ukuran_list]
        return hasil


class Kebutuhan(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draf"
        AKTIF = "aktif", "Aktif"
        SELESAI = "selesai", "Terpenuhi"

    lembaga = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kebutuhan"
    )
    nama_barang = models.CharField(max_length=120)
    kategori = models.CharField(max_length=30, choices=Kategori.choices, default=Kategori.LAINNYA)
    jumlah = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)
    terpenuhi = models.PositiveIntegerField(default=0)
    ukuran = models.CharField(max_length=100, blank=True, help_text="Dipisah koma, mis. '6 th,8 th'")
    kondisi_min = models.CharField(max_length=20, choices=KONDISI_MIN_CHOICES, default=Kondisi.TERAWAT)
    tenggat = models.DateField(null=True, blank=True)
    foto_url = models.URLField(blank=True)
    cerita = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    dibuat = models.DateTimeField(auto_now_add=True)
    diubah = models.DateTimeField(auto_now=True)

    objects = KebutuhanQuerySet.as_manager()

    class Meta:
        ordering = ["-dibuat"]
        verbose_name_plural = "kebutuhan"

    def __str__(self):
        return f"{self.nama_barang} ({self.terpenuhi}/{self.jumlah})"

    @property
    def nama_lembaga(self):
        if hasattr(self.lembaga, "institution_profile") and self.lembaga.institution_profile.name:
            return self.lembaga.institution_profile.name
        return self.lembaga.get_full_name() or self.lembaga.username

    @property
    def ukuran_list(self):
        return [u for u in self.ukuran.split(",") if u]

    @property
    def ukuran_label(self):
        return ", ".join(self.ukuran_list)

    @property
    def sisa(self):
        return max(self.jumlah - self.terpenuhi, 0)

    @property
    def persen(self):
        if not self.jumlah:
            return 0
        return min(round(self.terpenuhi * 100 / self.jumlah), 100)

    @property
    def kedaluwarsa(self):
        return bool(self.tenggat and self.tenggat < timezone.localdate())

    def tambah_terpenuhi(self, n):
        self.terpenuhi += n
        if self.terpenuhi >= self.jumlah and self.status == self.Status.AKTIF:
            self.status = self.Status.SELESAI
        self.save(update_fields=["terpenuhi", "status", "diubah"])

class Penawaran(models.Model):
    class Status(models.TextChoices):
        MENUNGGU = "menunggu", "Menunggu keputusan"
        DITERIMA = "diterima", "Diterima, menunggu barang"
        DITOLAK = "ditolak", "Ditolak"
        SELESAI = "selesai", "Barang diterima"

    class Metode(models.TextChoices):
        ANTAR = "antar", "Antar sendiri"
        KURIR = "kurir", "Pakai kurir"

    class Jam(models.TextChoices):
        PAGI = "pagi", "Pagi (09–12)"
        SIANG = "siang", "Siang (12–15)"
        SORE = "sore", "Sore (15–16)"

    donatur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tawaran_donasi"
    )
    lembaga = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tawaran_masuk"
    )
    kebutuhan = models.ForeignKey(
        Kebutuhan, on_delete=models.SET_NULL, null=True, blank=True, related_name="penawaran"
    )
    
    lemari_id = models.CharField(max_length=50, blank=True)
    nama_barang = models.CharField(max_length=120)
    ukuran = models.CharField(max_length=30, blank=True)
    kondisi = models.CharField(max_length=20, choices=Kondisi.choices, default=Kondisi.TERAWAT)
    jumlah = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)
    foto_url = models.URLField(blank=True)

    metode = models.CharField(max_length=10, choices=Metode.choices, default=Metode.ANTAR)
    tanggal_rencana = models.DateField(null=True, blank=True)
    jam = models.CharField(max_length=10, choices=Jam.choices, default=Jam.PAGI)
    pesan = models.TextField(blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.MENUNGGU)
    dibuat = models.DateTimeField(auto_now_add=True)
    diputuskan_pada = models.DateTimeField(null=True, blank=True)
    diterima_pada = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-dibuat"]
        verbose_name_plural = "penawaran"

    def __str__(self):
        return f"{self.jumlah} {self.nama_barang} → {self.lembaga} ({self.status})"

    @property
    def nama_donatur(self):
        return self.donatur.username

    def terima(self):
        if self.status != self.Status.MENUNGGU:
            return False
        self.status = self.Status.DITERIMA
        self.diputuskan_pada = timezone.now()
        self.save(update_fields=["status", "diputuskan_pada"])
        return True

    def tolak(self):
        if self.status != self.Status.MENUNGGU:
            return False
        self.status = self.Status.DITOLAK
        self.diputuskan_pada = timezone.now()
        self.save(update_fields=["status", "diputuskan_pada"])
        return True

    def selesaikan(self):
        """Lembaga menandai barang sudah diterima secara fisik."""
        if self.status != self.Status.DITERIMA:
            return False
        with transaction.atomic():
            self.status = self.Status.SELESAI
            self.diterima_pada = timezone.now()
            self.save(update_fields=["status", "diterima_pada"])
            if self.kebutuhan_id:
                self.kebutuhan.tambah_terpenuhi(self.jumlah)
            
            # Opsional: Jika barang berasal dari lemari_id, hapus atau nonaktifkan dari WardrobeItem
            if self.lemari_id:
                try:
                    from lemari.models import WardrobeItem
                    WardrobeItem.objects.filter(pk=self.lemari_id, owner=self.donatur).delete()
                except Exception:
                    pass
        return True