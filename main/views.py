from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages

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
    if request.method == 'POST':
        # Grab data using the 'name' attributes from register.html
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm = request.POST.get('confirm')

        if password != confirm:
            messages.error(request, 'Kata sandi tidak cocok.')
            return render(request, 'register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username sudah terpakai.')
            return render(request, 'register.html')
        
        # Create user in Django database
        User.objects.create_user(username=username, email=email, password=password)
        messages.success(request, 'Akun berhasil dibuat. Silakan masuk.')
        return redirect('main:show_login')

    return render(request, 'register.html')

def logout_user(request):
    logout(request)
    return redirect('main:show_main')