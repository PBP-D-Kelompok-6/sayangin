import os
import re
import secrets
from urllib.parse import urlencode
import requests
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core import serializers
from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST, require_GET
from main.models import UserProfile, UserAddress, InstitutionProfile
from main.forms import InstitutionProfileForm, ProfileForm, CITY_CHOICES
from main.decorators import personal_required, lembaga_required
from main.serializers import ChangePasswordSerializer, DeleteAccountSerializer
from main.services import (
    ensure_user_addresses_synced,
    filter_user_addresses,
    first_error_message,
    generate_unique_username,
    get_name_parts,
    is_institution_profile_complete,
)
from donasi.models import Kebutuhan, Penawaran
from impact.views import get_user_impact_summary
from marketplace.models import Order, Product
from sayangin.wilayah import get_city_groups


def show_main(request):
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.role == 'LEMBAGA' and not is_institution_profile_complete(request.user):
            return redirect('main:edit_institution_profile')

    daftar_kebutuhan = Kebutuhan.objects.aktif().select_related("lembaga")[:5] # type: ignore
    
    return render(request, 'index.html', {
        'daftar_kebutuhan': daftar_kebutuhan,
    })


def show_menu(request):
    return render(request, 'menu.html')


def _is_safe_next_url(request, next_url: str) -> bool:
    return bool(
        next_url
        and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})
    )


def _redirect_authenticated_user(request, user, next_url: str = ''):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if profile.role == 'LEMBAGA':
        if not is_institution_profile_complete(user):
            return redirect('main:edit_institution_profile')
        if _is_safe_next_url(request, next_url):
            return redirect(next_url)
        return redirect('donasi:dashboard_lembaga')
    if _is_safe_next_url(request, next_url):
        return redirect(next_url)
    return redirect('main:show_main')


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
            if profile.role == 'LEMBAGA' and not is_institution_profile_complete(user):
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

        username = raw_username if raw_username else generate_unique_username(email)
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
    all_addresses = ensure_user_addresses_synced(request.user, profile)
    _, first_name, initials = get_name_parts(request.user, profile)

    primary_addr = all_addresses.filter(is_primary=True).first() or all_addresses.first()
    if primary_addr:
        formatted_address = primary_addr.formatted_address
    else:
        address_parts = [p for p in [profile.address, profile.city] if p]
        formatted_address = ", ".join(address_parts)
        if profile.postal_code:
            formatted_address = f"{formatted_address} {profile.postal_code}".strip()

    label_filter = (request.GET.get('label') or '').strip().upper()
    q = (request.GET.get('q') or '').strip()
    addresses = filter_user_addresses(all_addresses, label=label_filter, query=q)

    raw_next = (request.GET.get('next') or '').strip()
    next_url = raw_next if _is_safe_next_url(request, raw_next) else ''
    open_add_address = request.GET.get('add_address') in ('1', 'true', 'True')
    edit_address_id = (request.GET.get('edit_address') or '').strip()

    prefs = profile.get_preferences_dict()
    impact_summary = get_user_impact_summary(request.user)

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
        "city_groups": get_city_groups(),
        "address_label_choices": UserProfile.ADDRESS_LABEL_CHOICES,
        "next_url": next_url,
        "open_add_address": open_add_address,
        "edit_address_id": edit_address_id,
        "has_usable_password": request.user.has_usable_password(),
        "pesanan_berjalan": Order.objects.filter(buyer=request.user).exclude(status='selesai').count(),
        "barang_tayang": Product.objects.filter(seller=request.user).available().count(),
        "donasi_tersalurkan": Penawaran.objects.filter(donatur=request.user, status=Penawaran.Status.SELESAI).count(),
        "impact_summary": impact_summary,
        "impact_points": impact_summary["points"],
        "impact_badges_count": impact_summary["earned_badges"],
        "impact_wardrobe_count": impact_summary["wardrobe_count"],
    }

    return render(request, 'profil.html', context)


@login_required(login_url='main:show_login')
def edit_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.role == 'LEMBAGA':
        return redirect('main:edit_institution_profile')
    ensure_user_addresses_synced(request.user, profile)

    mode = (request.POST.get('mode') or request.GET.get('mode') or '').strip().lower()
    address_id = request.POST.get('address_id') or request.GET.get('address_id')
    raw_next = (request.POST.get('next') or request.GET.get('next') or '').strip()
    next_url = raw_next if _is_safe_next_url(request, raw_next) else ''
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
            province_val = (post_data.get("province") or "").strip()
            district_val = (post_data.get("district") or "").strip()
            subdistrict_val = (post_data.get("subdistrict") or "").strip()
            ro_dest_val = (post_data.get("rajaongkir_destination_id") or "").strip()
            is_primary_val = bool(form.cleaned_data.get("is_primary_address"))

            saved_addr = None
            if addr_text or city_text:
                if target_address and mode != 'add':
                    city_changed = target_address.city.strip().lower() != city_text.lower()
                    target_address.label = label_val
                    target_address.recipient_name = saved_profile.full_name
                    target_address.phone_number = saved_profile.phone_number
                    target_address.address = addr_text
                    target_address.city = city_text
                    target_address.postal_code = postal_val
                    if province_val:
                        target_address.province = province_val
                    elif city_changed:
                        target_address.province = ""
                    if district_val or city_changed:
                        target_address.district = district_val
                    if subdistrict_val or city_changed:
                        target_address.subdistrict = subdistrict_val
                    if ro_dest_val or city_changed:
                        target_address.rajaongkir_destination_id = ro_dest_val
                    target_address.is_primary = is_primary_val
                    target_address.save()
                    saved_addr = target_address
                else:
                    saved_addr = UserAddress.objects.create(
                        user=request.user,
                        label=label_val,
                        recipient_name=saved_profile.full_name,
                        phone_number=saved_profile.phone_number,
                        address=addr_text,
                        subdistrict=subdistrict_val,
                        district=district_val,
                        city=city_text,
                        province=province_val,
                        rajaongkir_destination_id=ro_dest_val,
                        postal_code=postal_val,
                        is_primary=is_primary_val,
                    )

            messages.success(request, "Profil anda berhasil diperbarui.")
            if next_url:
                if saved_addr:
                    sep = "&" if "?" in next_url else "?"
                    return redirect(f"{next_url}{sep}address_id={saved_addr.pk}")
                return redirect(next_url)
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
        "city_groups": get_city_groups(),
        "next_url": next_url,
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
    all_addresses = ensure_user_addresses_synced(request.user, profile)
    addresses = filter_user_addresses(
        all_addresses,
        label=request.GET.get('label', ''),
        query=request.GET.get('q', ''),
    )
    data = serializers.serialize('json', addresses)
    return HttpResponse(data, content_type="application/json")


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
        username = generate_unique_username(google_email)
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
        if not is_institution_profile_complete(user):
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
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.POST.dict(), context={"request": request})
    if serializer.is_valid():
        serializer.save()
        messages.success(request, "Kata sandi berhasil diperbarui.")
    else:
        messages.error(request, first_error_message(serializer.errors))
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.role == 'LEMBAGA':
        return redirect('main:show_lembaga_profile')
    return redirect('main:show_profile')


@login_required(login_url='main:show_login')
@require_POST
def delete_account(request):
    serializer = DeleteAccountSerializer(data=request.POST.dict(), context={"request": request})
    if not serializer.is_valid():
        messages.error(request, first_error_message(serializer.errors))
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