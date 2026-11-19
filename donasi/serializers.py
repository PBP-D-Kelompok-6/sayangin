from rest_framework import serializers
from django.utils import timezone
from .models import Kebutuhan, Penawaran, Kondisi, Kategori


class KebutuhanSerializer(serializers.ModelSerializer):
    nama_lembaga = serializers.ReadOnlyField()
    ukuran_list = serializers.ReadOnlyField()
    sisa = serializers.ReadOnlyField()
    persen = serializers.ReadOnlyField()
    kedaluwarsa = serializers.ReadOnlyField()
    jumlah_tawaran_menunggu = serializers.SerializerMethodField()

    class Meta:
        model = Kebutuhan
        fields = [
            "id",
            "nama_lembaga",
            "nama_barang",
            "kategori",
            "jumlah",
            "terpenuhi",
            "sisa",
            "persen",
            "ukuran",
            "ukuran_list",
            "kondisi_min",
            "tenggat",
            "foto_url",
            "cerita",
            "status",
            "kedaluwarsa",
            "jumlah_tawaran_menunggu",
            "dibuat",
            "diubah",
        ]
        read_only_fields = ["id", "terpenuhi", "dibuat", "diubah"]

    def get_jumlah_tawaran_menunggu(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.penawaran.filter(status=Penawaran.Status.MENUNGGU).count()
        return 0

    def validate_tenggat(self, value):
        instance = getattr(self, "instance", None)
        # Jika sedang update data dan tenggat tidak diubah, izinkan nilai lama
        if instance and instance.tenggat == value:
            return value
        if value and value < timezone.localdate():
            raise serializers.ValidationError("Tenggat waktu tidak boleh di masa lalu.")
        return value

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        jumlah = attrs.get("jumlah", instance.jumlah if instance else 0)
        terpenuhi = instance.terpenuhi if instance else 0

        if instance and jumlah < terpenuhi:
            raise serializers.ValidationError({
                "jumlah": f"Jumlah tidak boleh kurang dari barang yang sudah terpenuhi ({terpenuhi})."
            })
        return attrs


class PenawaranSerializer(serializers.ModelSerializer):
    donatur_username = serializers.ReadOnlyField(source="donatur.username")
    nama_lembaga = serializers.SerializerMethodField()
    kebutuhan_nama = serializers.ReadOnlyField(source="kebutuhan.nama_barang", default="")

    class Meta:
        model = Penawaran
        fields = [
            "id",
            "kebutuhan",
            "kebutuhan_nama",
            "lembaga",
            "nama_lembaga",
            "donatur",
            "donatur_username",
            "lemari_id",
            "nama_barang",
            "ukuran",
            "kondisi",
            "jumlah",
            "foto_url",
            "metode",
            "tanggal_rencana",
            "jam",
            "pesan",
            "status",
            "dibuat",
            "diputuskan_pada",
            "diterima_pada",
        ]
        read_only_fields = [
            "id",
            "donatur",
            "lembaga",
            "status",
            "dibuat",
            "diputuskan_pada",
            "diterima_pada",
        ]

    def get_nama_lembaga(self, obj):
        if hasattr(obj.lembaga, "institution_profile") and obj.lembaga.institution_profile.name:
            return obj.lembaga.institution_profile.name
        return obj.lembaga.get_full_name() or obj.lembaga.username

    def validate_tanggal_rencana(self, value):
        if value and value < timezone.localdate():
            raise serializers.ValidationError("Tanggal rencana donasi tidak boleh di masa lalu.")
        return value

    def validate(self, attrs):
        kebutuhan = attrs.get("kebutuhan")
        tanggal_rencana = attrs.get("tanggal_rencana")

        if kebutuhan and kebutuhan.tenggat and tanggal_rencana:
            if tanggal_rencana > kebutuhan.tenggat:
                tenggat_fmt = kebutuhan.tenggat.strftime("%d %b %Y")
                raise serializers.ValidationError({
                    "tanggal_rencana": f"Tanggal rencana tidak boleh melebihi tenggat lembaga ({tenggat_fmt})."
                })
        return attrs