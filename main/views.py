import json
import os
import re
import secrets
from urllib.parse import urlencode
import requests
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core import serializers
from django.http import HttpResponse, JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST, require_GET
from main.models import UserProfile, UserAddress, InstitutionProfile
from main.forms import InstitutionProfileForm, ProfileForm, UserAddressForm, CITY_CHOICES
from main.decorators import personal_required, lembaga_required
from donasi.models import Kebutuhan, Penawaran
from marketplace.models import Order, Product


def show_main(request):
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.role == 'LEMBAGA' and not _is_institution_profile_complete(request.user):
            return redirect('main:edit_institution_profile')

    daftar_kebutuhan = Kebutuhan.objects.aktif().select_related("lembaga")[:5] # type: ignore
    
    return render(request, 'index.html', {
        'daftar_kebutuhan': daftar_kebutuhan,
    })


def show_menu(request):
    return render(request, 'menu.html')


def _is_institution_profile_complete(user) -> bool:
    institution = InstitutionProfile.objects.filter(user=user).first()
    return bool(institution and institution.name.strip() and institution.address.strip())


def _is_safe_next_url(request, next_url: str) -> bool:
    return bool(
        next_url
        and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})
    )


def _redirect_authenticated_user(request, user, next_url: str = ''):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if profile.role == 'LEMBAGA':
        if not _is_institution_profile_complete(user):
            return redirect('main:edit_institution_profile')
        if _is_safe_next_url(request, next_url):
            return redirect(next_url)
        return redirect('donasi:dashboard_lembaga')
    if _is_safe_next_url(request, next_url):
        return redirect(next_url)
    return redirect('main:show_main')


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
    next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()
    if request.user.is_authenticated:
        return _redirect_authenticated_user(request, request.user, next_url)

    if request.method == 'POST':
        identity = (request.POST.get('identity') or request.POST.get('email') or '').strip()
        password = request.POST.get('password', "")

        user_obj = User.objects.filter(email__iexact=identity).first()
        user_to_auth = user_obj.username if user_obj else identity
        user = authenticate(request, username=user_to_auth, password=password)

        if user is not None:
            login(request, user)
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if profile.role == 'LEMBAGA' and not _is_institution_profile_complete(user):
                messages.info(request, 'Silakan lengkapi profil lembaga Anda terlebih dahulu.')
                return redirect('main:edit_institution_profile')
            return _redirect_authenticated_user(request, user, next_url)
        else:
            messages.error(request, 'Email/username atau kata sandi salah.')
            return render(request, 'login.html', {
                'identity_value': identity,
                'login_error': True,
                'next_url': next_url,
            })

    return render(request, 'login.html', {'next_url': next_url})


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
    next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()
    if request.user.is_authenticated:
        return _redirect_authenticated_user(request, request.user, next_url)

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

    show_cart_notice = bool(next_url and 'checkout' in next_url.lower()) or request.GET.get('from') == 'checkout'

    context = {
        'account_type': account_type,
        'is_lembaga': account_type == 'LEMBAGA',
        'next_url': next_url,
        'show_cart_notice': show_cart_notice,
        'errors': {},
        'email_value': request.GET.get('email', '').strip(),  # dibawa dari form email di footer
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
def show_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.role == 'LEMBAGA':
        return redirect('main:show_lembaga_profile')
    all_addresses = _ensure_user_addresses_synced(request.user, profile)
    display_name = (profile.full_name or request.user.username).strip()
    parts = display_name.split()
    first_name = parts[0] if parts else request.user.username
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[1][0]).upper()
    else:
        initials = display_name[:2].upper()

    primary_addr = all_addresses.filter(is_primary=True).first() or all_addresses.first()
    if primary_addr:
        formatted_address = primary_addr.formatted_address
    else:
        address_parts = [p for p in [profile.address, profile.city] if p]
        formatted_address = ", ".join(address_parts)
        if profile.postal_code:
            formatted_address = f"{formatted_address} {profile.postal_code}".strip()

    addresses = all_addresses
    label_filter = (request.GET.get('label') or '').strip().upper()
    if label_filter and label_filter != 'ALL':
        addresses = addresses.filter(label=label_filter)

    q = (request.GET.get('q') or '').strip()
    if q:
        addresses = addresses.filter(
            Q(address__icontains=q) |
            Q(city__icontains=q) |
            Q(recipient_name__icontains=q)
        )

    prefs = profile.get_preferences_dict()

    context = {
        "profile": profile,
        "addresses": addresses,
        "selected_label": label_filter or 'ALL',
        "search_query": q,
        "total_addresses_count": all_addresses.count(),
        "preferences": prefs,
        "first_name": first_name,
        "initials": initials,
        "formatted_address": formatted_address,
        "city_choices": [c for c in CITY_CHOICES if c[0]],
        "address_label_choices": UserProfile.ADDRESS_LABEL_CHOICES,
        "has_usable_password": request.user.has_usable_password(),
        "pesanan_berjalan": Order.objects.filter(buyer=request.user).exclude(status='selesai').count(),
        "barang_tayang": Product.objects.filter(seller=request.user).available().count(),
        "donasi_tersalurkan": Penawaran.objects.filter(donatur=request.user, status=Penawaran.Status.SELESAI).count(),
    }

    return render(request, 'profil.html', context)


@login_required(login_url='main:show_login')
def edit_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.role == 'LEMBAGA':
        return redirect('main:edit_institution_profile')
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
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    _ensure_user_addresses_synced(request.user, profile)

    addresses = UserAddress.objects.filter(user=request.user)
    label_filter = (request.GET.get('label') or '').strip().upper()
    if label_filter and label_filter != 'ALL':
        addresses = addresses.filter(label=label_filter)

    q = (request.GET.get('q') or '').strip()
    if q:
        addresses = addresses.filter(
            Q(address__icontains=q) |
            Q(city__icontains=q) |
            Q(recipient_name__icontains=q)
        )

    data = serializers.serialize('json', addresses)
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

    label_filter = (request.GET.get('label') or '').strip().upper()
    if label_filter and label_filter != 'ALL':
        addresses = addresses.filter(label=label_filter)

    q = (request.GET.get('q') or '').strip()
    if q:
        addresses = addresses.filter(
            Q(address__icontains=q) |
            Q(city__icontains=q) |
            Q(recipient_name__icontains=q)
        )

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


def google_login(request):
    """
    Initiates Google OAuth 2.0 login / registration / account linking.
    If GOOGLE_CLIENT_ID & GOOGLE_CLIENT_SECRET are configured in the environment,
    redirects to Google's OAuth 2.0 authorization endpoint.
    Otherwise renders the built-in Sayangin x Google account selector so the flow
    works out-of-the-box in local development and automated tests.
    """
    jenis = (request.GET.get('jenis') or request.GET.get('tipe') or 'pribadi').strip().lower()
    action = (request.GET.get('action') or 'login').strip().lower()
    next_url = (request.GET.get('next') or '').strip()

    state = secrets.token_urlsafe(24)
    request.session['google_oauth_state'] = state
    request.session['google_oauth_jenis'] = 'lembaga' if jenis == 'lembaga' else 'pribadi'
    request.session['google_oauth_action'] = action
    if next_url:
        request.session['google_oauth_next'] = next_url

    client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()

    if client_id and client_secret and request.GET.get('mode') != 'chooser':
        redirect_uri = request.build_absolute_uri(reverse('main:google_callback'))
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'prompt': 'select_account',
        }
        return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")

    return render(request, 'google_oauth.html', {
        'state': state,
        'is_lembaga': jenis == 'lembaga',
        'action': action,
        'next_url': next_url,
    })


def google_callback(request):
    """
    Handles the Google OAuth 2.0 callback (both live OAuth code exchange and
    the built-in development/test account chooser).
    """
    expected_state = request.session.get('google_oauth_state')
    incoming_state = (request.GET.get('state') or request.POST.get('state') or '').strip()
    if not expected_state or not incoming_state or expected_state != incoming_state:
        messages.error(request, "Sesi otentikasi Google tidak valid. Silakan coba lagi.")
        return redirect('main:show_login')

    action = (request.POST.get('action') or request.session.pop('google_oauth_action', 'login')).strip().lower()
    jenis = (request.POST.get('jenis') or request.session.pop('google_oauth_jenis', 'pribadi')).strip().lower()
    next_url = (request.POST.get('next') or request.session.pop('google_oauth_next', '')).strip()
    request.session.pop('google_oauth_state', None)

    google_email = ''
    google_name = ''

    code = request.GET.get('code')
    client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()

    if code and client_id and client_secret:
        redirect_uri = request.build_absolute_uri(reverse('main:google_callback'))
        try:
            token_res = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'code': code,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri,
                    'grant_type': 'authorization_code',
                },
                timeout=10,
            )
            token_data = token_res.json()
            access_token = token_data.get('access_token')
            if access_token:
                userinfo_res = requests.get(
                    'https://www.googleapis.com/oauth2/v3/userinfo',
                    headers={'Authorization': f'Bearer {access_token}'},
                    timeout=10,
                )
                userinfo = userinfo_res.json()
                google_email = (userinfo.get('email') or '').strip().lower()
                google_name = (userinfo.get('name') or '').strip()
        except requests.RequestException:
            messages.error(request, "Gagal menghubungi layanan Google. Silakan coba lagi.")
            return redirect('main:show_login')
    elif request.method == 'POST':
        google_email = (request.POST.get('email') or '').strip().lower()
        google_name = (request.POST.get('full_name') or '').strip()

    if not google_email or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', google_email):
        messages.error(request, "Pilih atau masukkan alamat email Google yang valid.")
        return redirect('main:google_login')

    if not google_name:
        local_part = google_email.split('@')[0].replace('.', ' ').replace('_', ' ')
        google_name = local_part.title()

    # Case 1: Authenticated user linking their Google account from Profile page
    if request.user.is_authenticated and action == 'connect':
        conflict = UserProfile.objects.filter(
            google_connected=True,
            google_email__iexact=google_email,
        ).exclude(user=request.user).exists()
        if conflict:
            messages.error(request, "Akun Google tersebut sudah terhubung ke akun lain.")
        else:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.google_connected = True
            profile.google_email = google_email
            profile.save(update_fields=['google_connected', 'google_email'])
            messages.success(request, f"Akun Google ({google_email}) berhasil dihubungkan.")
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.role == 'LEMBAGA':
            return redirect('main:show_lembaga_profile')
        return redirect('main:show_profile')

    # Case 2: Login or Register with Google
    linked_profile = UserProfile.objects.filter(google_email__iexact=google_email).select_related('user').first()
    if linked_profile:
        user = linked_profile.user
        is_new_user = False
    else:
        user = User.objects.filter(email__iexact=google_email).first()
        is_new_user = user is None

    if is_new_user:
        username = _generate_unique_username(google_email)
        user = User(username=username, email=google_email)
        user.set_unusable_password()
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = 'LEMBAGA' if jenis == 'lembaga' else 'PERSONAL'
        profile.full_name = google_name
        profile.google_connected = True
        profile.google_email = google_email
        profile.save()
    else:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.google_connected = True
        profile.google_email = google_email
        if not profile.full_name.strip() and google_name:
            profile.full_name = google_name
        profile.save()

    login(request, user)

    if profile.role == 'LEMBAGA':
        if not _is_institution_profile_complete(user):
            return redirect('main:edit_institution_profile')
        if _is_safe_next_url(request, next_url):
            return redirect(next_url)
        return redirect('donasi:dashboard_lembaga')

    has_address = bool(profile.address.strip() or UserAddress.objects.filter(user=user).exists())
    if is_new_user or not has_address:
        return redirect('main:edit_profile')

    if _is_safe_next_url(request, next_url):
        return redirect(next_url)

    return redirect('main:show_main')


@login_required(login_url='main:show_login')
@require_POST
def api_disconnect_google(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not request.user.has_usable_password():
        return JsonResponse({
            "status": "error",
            "message": "Atur kata sandi terlebih dahulu sebelum memutuskan akun Google agar Anda tetap bisa masuk.",
        }, status=400)

    profile.google_connected = False
    profile.google_email = ''
    profile.save(update_fields=['google_connected', 'google_email'])
    return JsonResponse({
        "status": "ok",
        "message": "Akun Google berhasil diputuskan.",
        "google_connected": False,
        "connect_url": f"{reverse('main:google_login')}?action=connect",
    })


def _process_password_change(request, payload: dict) -> tuple[bool, dict, str]:
    user = request.user
    old_password = payload.get('old_password') or ''
    new_password1 = payload.get('new_password1') or ''
    new_password2 = payload.get('new_password2') or ''

    errors = {}
    if user.has_usable_password():
        if not old_password:
            errors['old_password'] = ['Masukkan kata sandi saat ini.']
        elif not user.check_password(old_password):
            errors['old_password'] = ['Kata sandi saat ini belum tepat.']

    if not new_password1 or len(new_password1) < 8:
        errors['new_password1'] = ['Kata sandi baru minimal 8 karakter.']
    elif new_password1 != new_password2:
        errors['new_password2'] = ['Konfirmasi kata sandi baru belum cocok.']

    if errors:
        first_msg = next(iter(errors.values()))[0]
        return False, errors, first_msg

    user.set_password(new_password1)
    user.save()
    update_session_auth_hash(request, user)

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.password_updated_at = timezone.now()
    profile.save(update_fields=['password_updated_at'])

    return True, {}, "Kata sandi berhasil diperbarui."


@login_required(login_url='main:show_login')
@require_POST
def api_change_password(request):
    payload = _parse_request_payload(request)
    ok, errors, message = _process_password_change(request, payload)
    if not ok:
        return JsonResponse({
            "status": "error",
            "message": message,
            "errors": errors,
        }, status=400)

    return JsonResponse({
        "status": "ok",
        "message": message,
        "has_usable_password": True,
        "password_status": "Baru saja diperbarui",
    })


@login_required(login_url='main:show_login')
@require_POST
def change_password(request):
    ok, _, message = _process_password_change(request, request.POST.dict())
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.role == 'LEMBAGA':
        return redirect('main:show_lembaga_profile')
    return redirect('main:show_profile')


def _validate_account_deletion(user, payload: dict) -> tuple[bool, str]:
    password = (payload.get('password') or '').strip()
    confirm_text = (payload.get('confirm_text') or '').strip().upper()

    if user.has_usable_password():
        if not password:
            return False, "Masukkan kata sandi Anda untuk mengonfirmasi penghapusan akun."

        if not user.check_password(password):
            return False, "Kata sandi Anda salah."

        return True, ""

    if not confirm_text:
        return False, "Ketik HAPUS untuk mengonfirmasi penghapusan akun."
    if confirm_text != 'HAPUS':
        return False, "Teks konfirmasi tidak cocok. Ketik Hapus dengan benar."

    return True, ""


@login_required(login_url='main:show_login')
@require_POST
def api_delete_account(request):
    payload = _parse_request_payload(request)
    ok, err_msg = _validate_account_deletion(request.user, payload)
    if not ok:
        return JsonResponse({
            "status": "error",
            "message": err_msg,
        }, status=400)

    user = request.user
    logout(request)
    user.delete()
    return JsonResponse({
        "status": "ok",
        "message": "Akun Anda telah dihapus.",
        "redirect_url": reverse('main:show_main'),
    })


@login_required(login_url='main:show_login')
@require_POST
def delete_account(request):
    ok, err_msg = _validate_account_deletion(request.user, request.POST.dict())
    if not ok:
        messages.error(request, err_msg)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.role == 'LEMBAGA':
            return redirect('main:show_lembaga_profile')
        return redirect('main:show_profile')

    user = request.user
    logout(request)
    user.delete()
    messages.info(request, "Akun Anda telah dihapus permanen.")
    return redirect('main:show_main')


@login_required(login_url='main:show_login')
def show_lembaga_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.role != 'LEMBAGA':
        return redirect('main:show_profile')
    institution = InstitutionProfile.objects.filter(user=request.user).first()
    if not institution or not institution.name.strip() or not institution.address.strip():
        messages.info(request, "Silakan lengkapi profil lembaga Anda terlebih dahulu.")
        return redirect("main:edit_institution_profile")
    context = {
        "lembaga": institution,
        "profile": profile,
        "has_usable_password": request.user.has_usable_password(),
        "is_owner": True,
    }

    return render(request, 'lembaga.html', context)


@login_required(login_url='main:show_login')
def edit_institution_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.role != 'LEMBAGA':
        return redirect('main:edit_profile')
    institution = InstitutionProfile.objects.filter(user=request.user).first()
    is_onboarding = not (institution and institution.name.strip() and institution.address.strip())
    email_value = request.user.email
    email_error = None

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

        if "email" in request.POST:
            email_value = (request.POST.get("email") or "").strip()
            if email_value and email_value.lower() != request.user.email.lower():
                if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email_value):
                    email_error = "Masukkan alamat email yang valid."
                elif User.objects.filter(email__iexact=email_value).exclude(pk=request.user.pk).exists():
                    email_error = "Email sudah terpakai oleh akun lain."

        form = InstitutionProfileForm(post_data, instance=institution)

        if form.is_valid() and not email_error:
            if "email" in request.POST and email_value and email_value.lower() != request.user.email.lower():
                request.user.email = email_value
                request.user.save(update_fields=["email"])

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
        "is_onboarding": is_onboarding,
        "email_value": email_value,
        "email_error": email_error,
    }

    return render(request, 'lembaga_profil.html', context)


@personal_required
def test_personal_access(request):
    return HttpResponse("Success! Anda akses halaman PERSONAL only.")


@lembaga_required
def test_lembaga_access(request):
    return HttpResponse("Success! Anda akses halaman LEMBAGA only.")