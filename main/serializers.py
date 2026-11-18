import json
import re

from django.contrib.auth import authenticate, update_session_auth_hash
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from donasi.models import Kebutuhan
from main.models import InstitutionProfile, UserAddress, UserProfile
from main.services import (
    generate_unique_username,
    get_name_parts,
    is_institution_profile_complete,
)


class LoginSerializer(serializers.Serializer):
    identity = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    username = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    email = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    password = serializers.CharField(write_only=True, allow_blank=True)

    def validate(self, attrs):
        identity = (
            attrs.get("identity")
            or attrs.get("username")
            or attrs.get("email")
            or ""
        ).strip()
        password = attrs.get("password") or ""
        if not identity or not password:
            raise serializers.ValidationError("Email/username dan kata sandi wajib diisi.")

        user_obj = User.objects.filter(email__iexact=identity).first()
        user_to_auth = user_obj.username if user_obj else identity
        user = authenticate(
            request=self.context.get("request"),
            username=user_to_auth,
            password=password,
        )
        if user is None:
            raise serializers.ValidationError("Email/username atau kata sandi salah.")
        if not user.is_active:
            raise serializers.ValidationError("Akun ini sedang nonaktif.")

        attrs["user"] = user
        return attrs


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    email = serializers.EmailField(
        required=True,
        error_messages={
            "required": "Masukkan alamat email yang valid.",
            "invalid": "Masukkan alamat email yang valid.",
            "blank": "Masukkan alamat email yang valid.",
        },
    )
    password = serializers.CharField(write_only=True, allow_blank=True)
    confirm = serializers.CharField(write_only=True, required=False, allow_blank=True)
    role = serializers.CharField(required=False, allow_blank=True)
    account_type = serializers.CharField(required=False, allow_blank=True)
    jenis = serializers.CharField(required=False, allow_blank=True)

    def validate_username(self, value):
        raw = (value or "").strip()
        if not raw:
            return ""
        if len(raw) < 3 or not re.match(r"^[A-Za-z0-9._]+$", raw):
            raise serializers.ValidationError(
                "Username minimal 3 karakter dan hanya boleh berisi huruf, angka, titik, atau garis bawah."
            )
        if User.objects.filter(username__iexact=raw).exists():
            raise serializers.ValidationError("Username sudah terpakai.")
        return raw

    def validate_email(self, value):
        email = (value or "").strip()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Email sudah terpakai.")
        return email

    def validate(self, attrs):
        password = attrs.get("password") or ""
        confirm = attrs.get("confirm", None)
        if len(password) < 8:
            raise serializers.ValidationError({"password": "Kata sandi minimal 8 karakter."})
        if confirm is not None and password != confirm:
            raise serializers.ValidationError({"password": "Kata sandi tidak cocok."})

        raw_jenis = (attrs.get("jenis") or "").strip().lower()
        raw_role = (attrs.get("role") or attrs.get("account_type") or "").strip().upper()
        attrs["resolved_role"] = (
            "LEMBAGA" if (raw_jenis == "lembaga" or raw_role == "LEMBAGA") else "PERSONAL"
        )
        return attrs

    def create(self, validated_data):
        username = validated_data.get("username") or generate_unique_username(validated_data["email"])
        user = User.objects.create_user(
            username=username,
            email=validated_data["email"],
            password=validated_data["password"],
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = validated_data["resolved_role"]
        profile.save(update_fields=["role"])
        user.profile = profile
        return user


class UserSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk", read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.SerializerMethodField()
    full_name = serializers.CharField(source="profile.full_name", read_only=True)
    phone_number = serializers.CharField(source="profile.phone_number", read_only=True)
    role = serializers.CharField(source="profile.role", read_only=True)
    google_connected = serializers.BooleanField(source="profile.google_connected", read_only=True)
    google_email = serializers.EmailField(source="profile.google_email", read_only=True)
    has_usable_password = serializers.SerializerMethodField()
    onboarding_complete = serializers.SerializerMethodField()

    def get_first_name(self, obj):
        profile, _ = UserProfile.objects.get_or_create(user=obj)
        _, first_name, _ = get_name_parts(obj, profile)
        return first_name

    def get_has_usable_password(self, obj):
        return obj.has_usable_password()

    def get_onboarding_complete(self, obj):
        profile, _ = UserProfile.objects.get_or_create(user=obj)
        if profile.role == "LEMBAGA":
            return is_institution_profile_complete(obj)
        return bool(profile.address.strip() or UserAddress.objects.filter(user=obj).exists())


class ProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(
        required=True,
        allow_blank=True,
        error_messages={"required": "Nama lengkap wajib diisi."},
    )
    email = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)

    def validate_full_name(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Nama lengkap wajib diisi.")
        return cleaned

    def validate_email(self, value):
        email = (value or "").strip()
        user = self.context["request"].user
        if email and email.lower() != (user.email or "").lower():
            if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
                raise serializers.ValidationError("Format email belum benar.")
            if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                raise serializers.ValidationError("Email sudah terpakai oleh akun lain.")
        return email

    def save(self, **kwargs):
        user = self.context["request"].user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        email = self.validated_data.get("email", "")
        if email and email.lower() != (user.email or "").lower():
            user.email = email
            user.save(update_fields=["email"])

        profile.full_name = self.validated_data["full_name"]
        if "phone_number" in self.validated_data:
            profile.phone_number = (self.validated_data["phone_number"] or "").strip()
        profile.save(update_fields=["full_name", "phone_number"])
        return profile


class PreferencesSerializer(serializers.Serializer):
    sizes = serializers.JSONField(required=False)
    categories = serializers.JSONField(required=False)
    reminder = serializers.JSONField(required=False)
    reminder_enabled = serializers.JSONField(required=False)
    email_newsletter = serializers.JSONField(required=False)
    email_news_enabled = serializers.JSONField(required=False)

    @staticmethod
    def _parse_list(value, fallback):
        if value is None:
            return fallback
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise serializers.ValidationError("Harus berupa daftar atau teks dipisah koma.")

    @staticmethod
    def _parse_bool(value, fallback):
        if value is None:
            return fallback
        if isinstance(value, str):
            return value.strip().lower() in ("true", "on", "1", "yes")
        return bool(value)

    def save(self, **kwargs):
        profile = self.context["profile"]
        current = profile.get_preferences_dict()
        data = self.validated_data

        sizes = self._parse_list(data.get("sizes"), current["sizes"])
        categories = self._parse_list(data.get("categories"), current["categories"])
        rem_raw = data.get("reminder", data.get("reminder_enabled"))
        em_raw = data.get("email_newsletter", data.get("email_news_enabled"))

        rem = self._parse_bool(rem_raw, current["reminder"])
        em = self._parse_bool(em_raw, current["email_newsletter"])

        new_prefs = {
            "sizes": sizes,
            "categories": categories,
            "reminder": rem,
            "email_newsletter": em,
            "reminder_enabled": rem,
            "email_news_enabled": em,
        }
        profile.preferences = json.dumps(new_prefs)
        profile.save(update_fields=["preferences"])
        return new_prefs


class UserAddressSerializer(serializers.ModelSerializer):
    label_display = serializers.CharField(source="get_label_display", read_only=True)
    formatted_address = serializers.CharField(read_only=True)

    class Meta:
        model = UserAddress
        fields = [
            "id",
            "label",
            "label_display",
            "recipient_name",
            "phone_number",
            "address",
            "subdistrict",
            "district",
            "city",
            "province",
            "rajaongkir_city_id",
            "rajaongkir_province_id",
            "rajaongkir_destination_id",
            "postal_code",
            "is_primary",
            "formatted_address",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "rajaongkir_city_id", "rajaongkir_province_id", "created_at", "updated_at"]
        extra_kwargs = {
            "address": {"required": False, "allow_blank": True},
            "city": {"required": False, "allow_blank": True},
            "label": {"required": False},
            "is_primary": {"required": False},
        }

    def to_internal_value(self, data):
        mutable = data.copy() if hasattr(data, "copy") else dict(data)
        aliases = (
            ("address", "alamat"),
            ("city", "kota"),
            ("postal_code", "kodepos"),
            ("label", "address_label"),
        )
        for target, alias in aliases:
            if target not in mutable and alias in mutable:
                mutable[target] = mutable[alias]

        if "label" in mutable:
            raw_label = str(mutable["label"] or "").strip().upper()
            if raw_label in dict(UserAddress.ADDRESS_LABEL_CHOICES):
                mutable["label"] = raw_label
            elif self.instance is not None:
                mutable["label"] = self.instance.label
            else:
                mutable["label"] = "RUMAH"

        if "is_primary" in mutable and isinstance(mutable["is_primary"], str):
            mutable["is_primary"] = mutable["is_primary"].strip().lower() in ("true", "on", "1", "yes")

        return super().to_internal_value(mutable)

    def validate(self, attrs):
        address = (attrs.get("address", getattr(self.instance, "address", "")) or "").strip()
        city = (attrs.get("city", getattr(self.instance, "city", "")) or "").strip()
        if not address or not city:
            raise serializers.ValidationError("Alamat lengkap dan kota wajib diisi.")
        attrs["address"] = address
        attrs["city"] = city
        for field in ("recipient_name", "phone_number", "subdistrict", "district", "province", "rajaongkir_destination_id", "postal_code"):
            if field in attrs and attrs[field] is not None:
                attrs[field] = attrs[field].strip()
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not validated_data.get("recipient_name"):
            validated_data["recipient_name"] = (profile.full_name or user.username).strip()
        if not validated_data.get("phone_number"):
            validated_data["phone_number"] = (profile.phone_number or "").strip()
        return UserAddress.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        new_city = validated_data.get("city", instance.city)
        city_changed = instance.city.strip().lower() != new_city.strip().lower()
        for field in ("province", "district", "subdistrict", "rajaongkir_destination_id"):
            if field not in validated_data and city_changed:
                setattr(instance, field, "")
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        return instance


class InstitutionProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    institution_type_display = serializers.CharField(source="get_institution_type_display", read_only=True)
    is_complete = serializers.SerializerMethodField()

    class Meta:
        model = InstitutionProfile
        fields = [
            "id",
            "username",
            "email",
            "name",
            "institution_type",
            "institution_type_display",
            "description",
            "address",
            "city",
            "rajaongkir_city_id",
            "person_in_charge",
            "contact_phone",
            "legal_document_name",
            "beneficiaries_count",
            "founded_year",
            "is_verified",
            "is_complete",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "rajaongkir_city_id", "is_verified", "created_at", "updated_at"]

    def get_is_complete(self, obj):
        return bool(obj.name.strip() and obj.address.strip())

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["email"] = instance.user.email
        return data

    def validate_name(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Nama lembaga wajib diisi.")
        return cleaned

    def validate_address(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Alamat lembaga wajib diisi.")
        return cleaned

    def validate_email(self, value):
        email = (value or "").strip()
        user = self.context["request"].user
        if email and email.lower() != (user.email or "").lower():
            if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
                raise serializers.ValidationError("Masukkan alamat email yang valid.")
            if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                raise serializers.ValidationError("Email sudah terpakai oleh akun lain.")
        return email

    def save(self, **kwargs):
        request = self.context["request"]
        user = request.user
        email = self.validated_data.pop("email", None)
        if email and email.lower() != (user.email or "").lower():
            user.email = email
            user.save(update_fields=["email"])

        uploaded_doc = request.FILES.get("legal_document") if hasattr(request, "FILES") else None
        if uploaded_doc:
            self.validated_data["legal_document_name"] = uploaded_doc.name

        if self.instance is None:
            return InstitutionProfile.objects.create(user=user, **self.validated_data)
        for attr, val in self.validated_data.items():
            setattr(self.instance, attr, val)
        self.instance.save()
        return self.instance


class InstitutionPublicSerializer(serializers.ModelSerializer):
    institution_type_display = serializers.CharField(source="get_institution_type_display", read_only=True)
    active_needs_count = serializers.SerializerMethodField()

    class Meta:
        model = InstitutionProfile
        fields = [
            "id",
            "name",
            "institution_type",
            "institution_type_display",
            "description",
            "address",
            "city",
            "beneficiaries_count",
            "founded_year",
            "is_verified",
            "active_needs_count",
        ]

    def get_active_needs_count(self, obj):
        return Kebutuhan.objects.aktif().filter(lembaga=obj.user).count()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=False, allow_blank=True, write_only=True)
    new_password1 = serializers.CharField(required=False, allow_blank=True, write_only=True)
    new_password2 = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user
        old_password = attrs.get("old_password") or ""
        new_password1 = attrs.get("new_password1") or ""
        new_password2 = attrs.get("new_password2") or ""

        errors = {}
        if user.has_usable_password():
            if not old_password:
                errors["old_password"] = "Masukkan kata sandi saat ini."
            elif not user.check_password(old_password):
                errors["old_password"] = "Kata sandi saat ini belum tepat."

        if not new_password1 or len(new_password1) < 8:
            errors["new_password1"] = "Kata sandi baru minimal 8 karakter."
        elif new_password1 != new_password2:
            errors["new_password2"] = "Konfirmasi kata sandi baru belum cocok."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def save(self, **kwargs):
        request = self.context["request"]
        user = request.user
        user.set_password(self.validated_data["new_password1"])
        user.save()
        django_request = getattr(request, "_request", request)
        update_session_auth_hash(django_request, user)

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.password_updated_at = timezone.now()
        profile.save(update_fields=["password_updated_at"])
        return profile


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)
    confirm_text = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user
        password = (attrs.get("password") or "").strip()
        confirm_text = (attrs.get("confirm_text") or "").strip().upper()

        if user.has_usable_password():
            if not password:
                raise serializers.ValidationError(
                    "Masukkan kata sandi Anda untuk mengonfirmasi penghapusan akun."
                )
            if not user.check_password(password):
                raise serializers.ValidationError("Kata sandi Anda salah.")
            return attrs

        if not confirm_text:
            raise serializers.ValidationError("Ketik HAPUS untuk mengonfirmasi penghapusan akun.")
        if confirm_text != "HAPUS":
            raise serializers.ValidationError("Teks konfirmasi tidak cocok. Ketik Hapus dengan benar.")
        return attrs
