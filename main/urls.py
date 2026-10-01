from django.urls import path
from main.views import show_main, show_login, show_register, logout_user
app_name = 'main'

urlpatterns = [
    path('', show_main, name='show_main'),
    path('login/', show_login, name='show_login'),
    path('register/', show_register, name='show_register'),
    path('logout/', logout_user, name='logout_user')
]