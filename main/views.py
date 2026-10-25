from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from main.models import UserProfile, InstitutionProfile
from main.forms import InstitutionProfileForm
from main.decorators import personal_required, lembaga_required

def show_main(request):
    return render(request, 'index.html')

def show_login(request):
    if request.method == 'POST':
        # Grab data using the 'name' attributes from login.html
        identity = request.POST.get('identity') 
        password = request.POST.get('password')

        try:
            user_obj = User.objects.get(email=identity)
            user_to_auth = user_obj.username
        except User.DoesNotExist:
            user_to_auth = identity

        # Check if user exists with these credentials
        user = authenticate(request, username=user_to_auth, password=password)

        if user is not None:
            login(request, user)
            return redirect('main:show_main')
        else:
            messages.error(request, 'Invalid username/email or password.')

    return render(request, 'login.html')

def show_register(request):
    if request.method == "POST":
        account_type = request.POST.get('account_type', 'PERSONAL')
    else:
        account_type = ('LEMBAGA' if request.GET.get('tipe') == 'lembaga' else 'PERSONAL')

    if account_type not in ('PERSONAL', 'LEMBAGA'):
        account_type = 'PERSONAL'

    context = {
        'account_type': account_type,
        'is_lembaga': account_type == 'LEMBAGA',
    }


    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password')
        confirm = request.POST.get('confirm')

        if password != confirm:
            messages.error(request, 'Kata sandi tidak cocok.')
            return render(request, 'register.html', context)
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username sudah terpakai.')
            return render(request, 'register.html', context)

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'Email sudah terpakai.')
            return render(request, 'register.html', context)
        
        new_user = User.objects.create_user(username=username, email=email, password=password)
        profile, created = UserProfile.objects.get_or_create(user=new_user)

        profile.role = account_type
        profile.save(update_fields=['role'])

        messages.success(request, 'Akun berhasil dibuat. Silakan masuk.')
        return redirect('main:show_login')

    return render(request, 'register.html', context)

@login_required(login_url='main:show_login')
def show_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    context = {
        "profile": profile,
    }

    return render(request, 'profil.html', context)

@require_POST
def logout_user(request):
    logout(request)
    return redirect('main:show_main')

@login_required(login_url='main:show_login') # type: ignore
def edit_institution_profile(request):
    user_profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )
    if user_profile.role != "LEMBAGA":
        raise PermissionDenied("Halaman ini hanya dapat diakses oleh lembaga.")

    institution = InstitutionProfile.objects.filter(user=request.user).first()
    if request.method == "POST":
        form = InstitutionProfileForm(request.POST, instance=institution)

        if form.is_valid():
            institution = form.save(commit=False)
            institution.user = request.user
            institution.save()

            messages.success(request, "Profil lembaga berhasil disimpan.")

            return redirect("main:edit_institution_profile")
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