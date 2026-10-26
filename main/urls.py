from django.urls import path
from main import views
app_name = 'main'

urlpatterns = [
    path('', views.show_main, name='show_main'),
    path('login/', views.show_login, name='show_login'),
    path('register/', views.show_register, name='show_register'),
    path('logout/', views.logout_user, name='logout_user'),
    path('profil/', views.show_profile, name='show_profile'),
    path('lembaga/profil/', views.edit_institution_profile, name='edit_institution_profile'),
    path('test/personal/', views.test_personal_access, name='test_personal_access'),
    path('test/lembaga/', views.test_lembaga_access, name='test_lembaga_access')
]