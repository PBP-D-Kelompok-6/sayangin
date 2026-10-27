import re
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from main.models import UserProfile, InstitutionProfile
from main.forms import InstitutionProfileForm, ProfileForm
from main.decorators import personal_required, lembaga_required

def show_main(request):
    return render(request, 'index.html')

def show_menu(request):
    return render(request, 'menu.html')

def show_login(request):
    if request.user.is_authenticated:
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
                institution = InstitutionProfile.objects.filter(user=user).first()
                if not institution:
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
    display_name = (profile.full_name or request.user.username).strip()
    parts = display_name.split()
    first_name = parts[0] if parts else request.user.username
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[1][0]).upper()
    else:
        initials = display_name[:2].upper()

    address_parts = [p for p in [profile.address, profile.city] if p]
    formatted_address = ", ".join(address_parts)
    if profile.postal_code:
        formatted_address = f"{formatted_address} {profile.postal_code}".strip()

    context = {
        "profile": profile,
        "first_name": first_name,
        "initials": initials,
        "formatted_address": formatted_address,
    }

    return render(request, 'profil.html', context)

@login_required(login_url='main:show_login')
@personal_required
def edit_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
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
            form.save()
            messages.success(request, "Profil anda berhasil diperbarui.")
            return redirect('main:show_profile')
    else:
        form = ProfileForm(instance=profile)

    context = {
        "form": form,
        "profile": profile,
    }

    return render(request, "edit_profil.html", context)

@require_POST
def logout_user(request):
    logout(request)
    return redirect('main:show_main')

@login_required(login_url='main:show_login')
@lembaga_required
def show_lembaga_profile(request):
    institution = InstitutionProfile.objects.filter(user=request.user).first()
    if not institution:
        messages.warning(request, "Silakan lengkapi profil lembaga anda terlebih dahulu.")
        return redirect("main:edit_institution_profile")
    context = {
        "lembaga": institution,
        "is_owner": True,
    }

    return render(request, 'lembaga.html', context)

@login_required(login_url='main:show_login')
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

# TEMP FOR TESTING RBAC STUFF, REMEMBER TO REMOVE
# TEMP FOR TESTING RBAC STUFF, REMEMBER TO REMOVE
# TEMP FOR TESTING RBAC STUFF, REMEMBER TO REMOVE
# TEMP FOR TESTING RBAC STUFF, REMEMBER TO REMOVE
# TEMP FOR TESTING RBAC STUFF, REMEMBER TO REMOVE

@personal_required
def test_personal_access(request):
    return HttpResponse("Success! Anda akses halaman PERSONAL only.")

@lembaga_required
def test_lembaga_access(request):
    return HttpResponse("Success! Anda akses halaman LEMBAGA only.")