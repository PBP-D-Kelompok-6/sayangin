import re

from django.contrib.auth.models import User
from django.db.models import Q

from main.models import InstitutionProfile, UserAddress, UserProfile


def is_institution_profile_complete(user) -> bool:
    institution = InstitutionProfile.objects.filter(user=user).first()
    return bool(institution and institution.name.strip() and institution.address.strip())


def ensure_user_addresses_synced(user, profile: UserProfile):
    """Ensure legacy flat UserProfile address fields are mirrored into UserAddress."""
    addresses_qs = UserAddress.objects.filter(user=user)
    if not addresses_qs.exists() and (profile.address.strip() or profile.city.strip()):
        UserAddress.objects.create(
            user=user,
            label=profile.address_label or 'RUMAH',
            recipient_name=profile.full_name,
            phone_number=profile.phone_number,
            address=profile.address,
            city=profile.city,
            postal_code=profile.postal_code,
            is_primary=True,
        )
    return UserAddress.objects.filter(user=user)


def filter_user_addresses(addresses, label: str = '', query: str = ''):
    label_filter = (label or '').strip().upper()
    if label_filter and label_filter != 'ALL':
        addresses = addresses.filter(label=label_filter)

    q = (query or '').strip()
    if q:
        addresses = addresses.filter(
            Q(address__icontains=q)
            | Q(district__icontains=q)
            | Q(subdistrict__icontains=q)
            | Q(city__icontains=q)
            | Q(province__icontains=q)
            | Q(postal_code__icontains=q)
            | Q(recipient_name__icontains=q)
        )
    return addresses


def generate_unique_username(email: str) -> str:
    local_part = email.split('@')[0].lower() if '@' in email else email.lower()
    cleaned = re.sub(r'[^a-z0-9._]+', '_', local_part).strip('._')
    if len(cleaned) < 3:
        cleaned = (cleaned + 'user')[:4] if cleaned else 'pengguna'
    base = cleaned[:24]
    candidate = base
    counter = 1
    while User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{base}{counter}"
        counter += 1
    return candidate


def get_name_parts(user, profile: UserProfile) -> tuple[str, str, str]:
    display_name = (profile.full_name or user.username).strip()
    parts = display_name.split()
    first_name = parts[0] if parts else user.username
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[1][0]).upper()
    else:
        initials = display_name[:2].upper()
    return display_name, first_name, initials


def delete_user_address_and_sync(user, addr: UserAddress):
    was_primary = addr.is_primary
    addr.delete()

    remaining = UserAddress.objects.filter(user=user)
    if was_primary and remaining.exists():
        next_primary = remaining.first()
        if next_primary:
            next_primary.is_primary = True
            next_primary.save()
    elif not remaining.exists():
        UserProfile.objects.filter(user=user).update(
            address='',
            city='',
            postal_code='',
        )


def first_error_message(errors, default: str = "Periksa kembali data yang dimasukkan.") -> str:
    if isinstance(errors, dict):
        for val in errors.values():
            msg = first_error_message(val, default="")
            if msg:
                return msg
    elif isinstance(errors, (list, tuple)) and errors:
        return first_error_message(errors[0], default=default)
    elif errors:
        return str(errors)
    return default
