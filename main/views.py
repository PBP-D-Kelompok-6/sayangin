import json
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core import serializers
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from main.models import UserProfile, UserAddress, InstitutionProfile
from main.forms import InstitutionProfileForm, ProfileForm, UserAddressForm, CITY_CHOICES
from main.decorators import personal_required, lembaga_required


def show_main(request):
    return render(request, 'index.html')


def show_menu(request):
    return render(request, 'menu.html')


def _is_institution_profile_complete(user) -> bool:
    institution = InstitutionProfile.objects.filter(user=user).first()
    return bool(institution and institution.name.strip() and institution.address.strip())


def _ensure_user_addresses_synced(user, profile: UserProfile):
    """
    Ensures that if UserProfile has legacy/flat address fields populated
    but no UserAddress rows yet, an initial UserAddress is created and synced.
    """
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


def _parse_request_payload(request) -> dict:
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return {}
    return request.POST.dict()


def show_login(request):
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.role == 'LEMBAGA':
            if not _is_institution_profile_complete(request.user):
                return redirect('main:edit_institution_profile')
            return redirect('main:show_lembaga_profile')
        return redirect("main:show_main")

    if request.method == 'POST':
        identity = (request.POST.get('identity') or request.POST.get('email') or '').strip()
        password = request.POST.get('password', "")

        user_obj = User.objects.filter(email__iexact=identity).first()
        user_to_auth = user_obj.username if user_obj else identity
        user = authenticate(request, username=user_to_auth, password=password)

        if user is not None:
            login(request, user)
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if profile.role == 'LEMBAGA':
                if not _is_institution_profile_complete(user):
                    messages.info(request, 'Silakan lengkapi profil lembaga Anda terlebih dahulu.')
                    return redirect('main:edit_institution_profile')
                return redirect('main:show_lembaga_profile')
            return redirect('main:show_main')
        else:
            messages.error(request, 'Email/username atau kata sandi salah.')
            return render(request, 'login.html', {
                'identity_value': identity,
                'login_error': True,
            })

    return render(request, 'login.html')


def _generate_unique_username(email: str) -> str:
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


def show_register(request):
    if request.user.is_authenticated:
        return redirect("main:show_main")

    if request.method == "POST":
        jenis = request.POST.get('jenis', '').strip().lower()
        raw_account_type = request.POST.get('account_type', '').strip().upper()
        if jenis == 'lembaga' or raw_account_type == 'LEMBAGA':
            account_type = 'LEMBAGA'
        else:
            account_type = 'PERSONAL'
    else:
        tipe_param = (request.GET.get('tipe') or request.GET.get('jenis') or '').strip().lower()
        account_type = 'LEMBAGA' if tipe_param == 'lembaga' else 'PERSONAL'

    next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()
    show_cart_notice = bool(next_url and 'checkout' in next_url.lower()) or request.GET.get('from') == 'checkout'

    context = {
        'account_type': account_type,
        'is_lembaga': account_type == 'LEMBAGA',
        'next_url': next_url,
        'show_cart_notice': show_cart_notice,
        'errors': {},
    }

    if request.method == 'POST':
        raw_username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm')

        context["username_value"] = raw_username
        context["email_value"] = email

        errors = {}

        if raw_username:
            if len(raw_username) < 3 or not re.match(r'^[A-Za-z0-9._]+$', raw_username):
                errors['username'] = 'Username minimal 3 karakter dan hanya boleh berisi huruf, angka, titik, atau garis bawah.'
            elif User.objects.filter(username__iexact=raw_username).exists():
                errors['username'] = 'Username sudah terpakai.'

        if not email or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            errors['email'] = 'Masukkan alamat email yang valid.'
        elif User.objects.filter(email__iexact=email).exists():
            errors['email'] = 'Email sudah terpakai.'

        if len(password) < 8:
            errors['password'] = 'Kata sandi minimal 8 karakter.'
        elif confirm is not None and password != confirm:
            errors['password'] = 'Kata sandi tidak cocok.'

        if errors:
            context['errors'] = errors
            for msg in errors.values():
                messages.error(request, msg)
            return render(request, 'register.html', context)

        username = raw_username if raw_username else _generate_unique_username(email)
        new_user = User.objects.create_user(username=username, email=email, password=password)
        profile, _ = UserProfile.objects.get_or_create(user=new_user)

        profile.role = account_type
        profile.save(update_fields=['role'])

        login(request, new_user)

        if account_type == 'LEMBAGA':
            return redirect('main:edit_institution_profile')
        return redirect('main:edit_profile')

    return render(request, 'register.html', context)


@login_required(login_url='main:show_login')
@personal_required
def show_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    addresses = _ensure_user_addresses_synced(request.user, profile)
    display_name = (profile.full_name or request.user.username).strip()
    parts = display_name.split()
    first_name = parts[0] if parts else request.user.username
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[1][0]).upper()
    else:
        initials = display_name[:2].upper()

    primary_addr = addresses.filter(is_primary=True).first() or addresses.first()
    if primary_addr:
        formatted_address = primary_addr.formatted_address
    else:
        address_parts = [p for p in [profile.address, profile.city] if p]
        formatted_address = ", ".join(address_parts)
        if profile.postal_code:
            formatted_address = f"{formatted_address} {profile.postal_code}".strip()

    prefs = profile.get_preferences_dict()

    context = {
        "profile": profile,
        "addresses": addresses,
        "preferences": prefs,
        "first_name": first_name,
        "initials": initials,
        "formatted_address": formatted_address,
        "city_choices": [c for c in CITY_CHOICES if c[0]],
    }

    return render(request, 'profil.html', context)


@login_required(login_url='main:show_login')
@personal_required
def edit_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    _ensure_user_addresses_synced(request.user, profile)

    mode = (request.POST.get('mode') or request.GET.get('mode') or '').strip().lower()
    address_id = request.POST.get('address_id') or request.GET.get('address_id')
    target_address = None
    if address_id:
        target_address = UserAddress.objects.filter(user=request.user, pk=address_id).first()
    elif mode != 'add':
        target_address = UserAddress.objects.filter(user=request.user, is_primary=True).first() or UserAddress.objects.filter(user=request.user).first()

    if request.method == "POST":
        post_data = request.POST.copy()
        if not post_data.get("full_name") and post_data.get("nama"):
            post_data["full_name"] = post_data["nama"]
        if not post_data.get("phone_number") and post_data.get("hp"):
            post_data["phone_number"] = post_data["hp"]
        if not post_data.get("address_label") and post_data.get("label"):
            post_data["address_label"] = post_data["label"].strip().upper()
        if not post_data.get("address") and post_data.get("alamat"):
            post_data["address"] = post_data["alamat"]
        if not post_data.get("city") and post_data.get("kota") and post_data.get("kota") != "Pilih kota":
            post_data["city"] = post_data["kota"]
        if not post_data.get("postal_code") and post_data.get("kodepos"):
            post_data["postal_code"] = post_data["kodepos"]
        if "utama" in post_data and "is_primary_address" not in post_data:
            post_data["is_primary_address"] = post_data["utama"]

        form = ProfileForm(post_data, instance=profile)
        if form.is_valid():
            saved_profile = form.save()
            addr_text = (post_data.get("address") or "").strip()
            city_text = (post_data.get("city") or "").strip()
            label_val = (post_data.get("address_label") or "RUMAH").strip().upper()
            postal_val = (post_data.get("postal_code") or "").strip()
            is_primary_val = bool(form.cleaned_data.get("is_primary_address"))

            if addr_text or city_text:
                if target_address and mode != 'add':
                    target_address.label = label_val
                    target_address.recipient_name = saved_profile.full_name
                    target_address.phone_number = saved_profile.phone_number
                    target_address.address = addr_text
                    target_address.city = city_text
                    target_address.postal_code = postal_val
                    target_address.is_primary = is_primary_val
                    target_address.save()
                else:
                    UserAddress.objects.create(
                        user=request.user,
                        label=label_val,
                        recipient_name=saved_profile.full_name,
                        phone_number=saved_profile.phone_number,
                        address=addr_text,
                        city=city_text,
                        postal_code=postal_val,
                        is_primary=is_primary_val,
                    )

            messages.success(request, "Profil anda berhasil diperbarui.")
            return redirect('main:show_profile')
    else:
        initial = {}
        if mode == 'add':
            initial = {
                'address_label': 'RUMAH',
                'address': '',
                'city': '',
                'postal_code': '',
                'is_primary_address': not UserAddress.objects.filter(user=request.user).exists(),
            }
        elif target_address:
            initial = {
                'address_label': target_address.label,
                'address': target_address.address,
                'city': target_address.city,
                'postal_code': target_address.postal_code,
                'is_primary_address': target_address.is_primary,
            }
        form = ProfileForm(instance=profile, initial=initial)

    context = {
        "form": form,
        "profile": profile,
        "mode": mode,
        "target_address": target_address,
    }

    return render(request, "edit_profil.html", context)


@login_required(login_url='main:show_login')
@require_GET
def show_profile_json(request):
    """Returns UserProfile serialized using django.core.serializers."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    data = serializers.serialize("json", [profile])
    return HttpResponse(data, content_type="application/json")


@login_required(login_url='main:show_login')
@require_GET
def show_addresses_json(request):
    """Returns all UserAddress objects for the user serialized using django.core.serializers."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    addresses = _ensure_user_addresses_synced(request.user, profile)
    data = serializers.serialize("json", addresses)
    return HttpResponse(data, content_type="application/json")


@login_required(login_url='main:show_login')
@require_GET
def api_profile_data(request):
    """Returns structured JSON with user profile, preferences, and RajaOngkir-ready addresses."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    addresses = _ensure_user_addresses_synced(request.user, profile)
    display_name = (profile.full_name or request.user.username).strip()
    parts = display_name.split()
    first_name = parts[0] if parts else request.user.username
    primary_addr = addresses.filter(is_primary=True).first() or addresses.first()

    return JsonResponse({
        "status": "ok",
        "user": {
            "id": request.user.pk,
            "username": request.user.username,
            "email": request.user.email,
            "first_name": first_name,
            "full_name": profile.full_name,
            "phone_number": profile.phone_number,
            "role": profile.role,
        },
        "preferences": profile.get_preferences_dict(),
        "addresses": [a.to_dict() for a in addresses],
        "primary_address": primary_addr.to_dict() if primary_addr else None,
        "serialized_addresses": json.loads(serializers.serialize("json", addresses)),
    })


@login_required(login_url='main:show_login')
@personal_required
@require_POST
def api_add_address(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    _ensure_user_addresses_synced(request.user, profile)
    payload = _parse_request_payload(request)

    label = (payload.get('label') or payload.get('address_label') or 'RUMAH').strip().upper()
    if label not in dict(UserAddress.ADDRESS_LABEL_CHOICES):
        label = 'RUMAH'
    address_text = (payload.get('address') or payload.get('alamat') or '').strip()
    city = (payload.get('city') or payload.get('kota') or '').strip()
    postal_code = (payload.get('postal_code') or payload.get('kodepos') or '').strip()
    recipient_name = (payload.get('recipient_name') or profile.full_name or request.user.username).strip()
    phone_number = (payload.get('phone_number') or profile.phone_number or '').strip()
    raw_primary = payload.get('is_primary')
    is_primary = raw_primary in (True, 'true', 'True', 'on', '1', 1)

    if not address_text or not city:
        return JsonResponse({
            "status": "error",
            "message": "Alamat lengkap dan kota wajib diisi.",
        }, status=400)

    new_addr = UserAddress.objects.create(
        user=request.user,
        label=label,
        recipient_name=recipient_name,
        phone_number=phone_number,
        address=address_text,
        city=city,
        postal_code=postal_code,
        is_primary=is_primary,
    )
    all_addresses = UserAddress.objects.filter(user=request.user)
    return JsonResponse({
        "status": "ok",
        "message": "Alamat baru berhasil ditambahkan.",
        "address": new_addr.to_dict(),
        "addresses": [a.to_dict() for a in all_addresses],
    }, status=201)


@login_required(login_url='main:show_login')
@personal_required
@require_POST
def api_edit_address(request, address_id: int):
    addr = get_object_or_404(UserAddress, pk=address_id, user=request.user)
    payload = _parse_request_payload(request)

    label = (payload.get('label') or payload.get('address_label') or addr.label).strip().upper()
    if label in dict(UserAddress.ADDRESS_LABEL_CHOICES):
        addr.label = label

    address_text = (payload.get('address') or payload.get('alamat') or '').strip()
    city = (payload.get('city') or payload.get('kota') or '').strip()
    if not address_text or not city:
        return JsonResponse({
            "status": "error",
            "message": "Alamat lengkap dan kota wajib diisi.",
        }, status=400)

    addr.address = address_text
    addr.city = city
    if 'postal_code' in payload or 'kodepos' in payload:
        addr.postal_code = (payload.get('postal_code') or payload.get('kodepos') or '').strip()
    if 'recipient_name' in payload:
        addr.recipient_name = (payload.get('recipient_name') or '').strip()
    if 'phone_number' in payload:
        addr.phone_number = (payload.get('phone_number') or '').strip()
    if 'is_primary' in payload:
        addr.is_primary = payload.get('is_primary') in (True, 'true', 'True', 'on', '1', 1)

    addr.save()
    all_addresses = UserAddress.objects.filter(user=request.user)
    return JsonResponse({
        "status": "ok",
        "message": "Alamat berhasil diperbarui.",
        "address": addr.to_dict(),
        "addresses": [a.to_dict() for a in all_addresses],
    })


@login_required(login_url='main:show_login')
@personal_required
@require_POST
def api_delete_address(request, address_id: int):
    addr = get_object_or_404(UserAddress, pk=address_id, user=request.user)
    was_primary = addr.is_primary
    addr.delete()

    remaining = UserAddress.objects.filter(user=request.user)
    if was_primary and remaining.exists():
        next_primary = remaining.first()
        if next_primary:
            next_primary.is_primary = True
            next_primary.save()
    elif not remaining.exists():
        UserProfile.objects.filter(user=request.user).update(
            address='',
            city='',
            postal_code='',
        )

    return JsonResponse({
        "status": "ok",
        "message": "Alamat berhasil dihapus.",
        "addresses": [a.to_dict() for a in UserAddress.objects.filter(user=request.user)],
    })


@login_required(login_url='main:show_login')
@personal_required
@require_POST
def api_set_primary_address(request, address_id: int):
    addr = get_object_or_404(UserAddress, pk=address_id, user=request.user)
    addr.is_primary = True
    addr.save()
    all_addresses = UserAddress.objects.filter(user=request.user)
    return JsonResponse({
        "status": "ok",
        "message": "Alamat utama berhasil diubah.",
        "address": addr.to_dict(),
        "addresses": [a.to_dict() for a in all_addresses],
    })


@login_required(login_url='main:show_login')
@personal_required
@require_POST
def api_update_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    payload = _parse_request_payload(request)

    full_name = (payload.get('full_name') or '').strip()
    email = (payload.get('email') or '').strip()
    phone_number = (payload.get('phone_number') or '').strip()

    if not full_name:
        return JsonResponse({"status": "error", "message": "Nama lengkap wajib diisi."}, status=400)

    if email and email.lower() != request.user.email.lower():
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return JsonResponse({"status": "error", "message": "Format email belum benar."}, status=400)
        if User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
            return JsonResponse({"status": "error", "message": "Email sudah terpakai oleh akun lain."}, status=400)
        request.user.email = email
        request.user.save(update_fields=['email'])

    profile.full_name = full_name
    profile.phone_number = phone_number
    profile.save(update_fields=['full_name', 'phone_number'])

    parts = full_name.split()
    first_name = parts[0] if parts else request.user.username

    return JsonResponse({
        "status": "ok",
        "message": "Data diri berhasil diperbarui.",
        "user": {
            "username": request.user.username,
            "email": request.user.email,
            "first_name": first_name,
            "full_name": profile.full_name,
            "phone_number": profile.phone_number,
        },
    })


@login_required(login_url='main:show_login')
@personal_required
@require_POST
def api_update_preferences(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    payload = _parse_request_payload(request)

    current_prefs = profile.get_preferences_dict()
    sizes = payload.get('sizes', current_prefs['sizes'])
    if isinstance(sizes, str):
        sizes = [s.strip() for s in sizes.split(',') if s.strip()]
    categories = payload.get('categories', current_prefs['categories'])
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(',') if c.strip()]

    reminder_raw = payload.get('reminder', payload.get('reminder_enabled', current_prefs['reminder']))
    if isinstance(reminder_raw, str):
        reminder_enabled = reminder_raw.lower() in ('true', 'on', '1')
    else:
        reminder_enabled = bool(reminder_raw)

    email_raw = payload.get('email_newsletter', payload.get('email_news_enabled', current_prefs['email_newsletter']))
    if isinstance(email_raw, str):
        email_news_enabled = email_raw.lower() in ('true', 'on', '1')
    else:
        email_news_enabled = bool(email_raw)

    new_prefs = {
        'sizes': list(sizes),
        'categories': list(categories),
        'reminder': bool(reminder_enabled),
        'email_newsletter': bool(email_news_enabled),
        'reminder_enabled': bool(reminder_enabled),
        'email_news_enabled': bool(email_news_enabled),
    }
    profile.preferences = json.dumps(new_prefs)
    profile.save(update_fields=['preferences'])

    return JsonResponse({
        "status": "ok",
        "message": "Preferensi berhasil disimpan.",
        "preferences": new_prefs,
    })


@require_POST
def logout_user(request):
    logout(request)
    return redirect('main:show_main')


@login_required(login_url='main:show_login')
@lembaga_required
def show_lembaga_profile(request):
    institution = InstitutionProfile.objects.filter(user=request.user).first()
    if not institution or not institution.name.strip() or not institution.address.strip():
        messages.info(request, "Silakan lengkapi profil lembaga Anda terlebih dahulu.")
        return redirect("main:edit_institution_profile")
    context = {
        "lembaga": institution,
        "is_owner": True,
    }

    return render(request, 'lembaga.html', context)


@login_required(login_url='main:show_login')
@lembaga_required
def edit_institution_profile(request):
    institution = InstitutionProfile.objects.filter(user=request.user).first()
    if request.method == "POST":
        post_data = request.POST.copy()
        if not post_data.get("name") and post_data.get("nama_lembaga"):
            post_data["name"] = post_data["nama_lembaga"]
        if not post_data.get("institution_type") and post_data.get("jenis_lembaga"):
            raw_type = post_data["jenis_lembaga"].strip().upper().replace(" ", "_")
            post_data["institution_type"] = raw_type
        if not post_data.get("institution_type"):
            post_data["institution_type"] = InstitutionProfile.InstitutionType.PANTI_ASUHAN
        if not post_data.get("address") and post_data.get("alamat"):
            post_data["address"] = post_data["alamat"]
        if not post_data.get("person_in_charge") and post_data.get("pj"):
            post_data["person_in_charge"] = post_data["pj"]
        if not post_data.get("contact_phone") and post_data.get("hp"):
            post_data["contact_phone"] = post_data["hp"]

        form = InstitutionProfileForm(post_data, instance=institution)

        if form.is_valid():
            institution = form.save(commit=False)
            institution.user = request.user
            uploaded_doc = request.FILES.get("legal_document")
            if uploaded_doc:
                institution.legal_document_name = uploaded_doc.name
            institution.save()

            messages.success(request, "Profil lembaga berhasil disimpan.")

            return redirect("main:show_lembaga_profile")
    else:
        form = InstitutionProfileForm(instance=institution)

    context = {
        "form": form,
        "institution": institution,
    }

    return render(request, 'lembaga_profil.html', context)


@personal_required
def test_personal_access(request):
    return HttpResponse("Success! Anda akses halaman PERSONAL only.")


@lembaga_required
def test_lembaga_access(request):
    return HttpResponse("Success! Anda akses halaman LEMBAGA only.")