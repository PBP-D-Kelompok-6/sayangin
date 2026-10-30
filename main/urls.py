from django.urls import path
from main import views

app_name = 'main'

urlpatterns = [
    path('', views.show_main, name='show_main'),
    path('menu/', views.show_menu, name='show_menu'),
    path('login/', views.show_login, name='show_login'),
    path('register/', views.show_register, name='show_register'),
    path('logout/', views.logout_user, name='logout_user'),
    path('auth/google/', views.google_login, name='google_login'),
    path('auth/google/callback/', views.google_callback, name='google_callback'),
    path('profil/personal/', views.show_profile, name='show_profile'),
    path('profil/personal/edit/', views.edit_profile, name='edit_profile'),
    path('profil/lembaga/', views.show_lembaga_profile, name='show_lembaga_profile'),
    path('profil/lembaga/edit/', views.edit_institution_profile, name='edit_institution_profile'),
    path('profil/password/', views.change_password, name='change_password'),
    path('profil/hapus/', views.delete_account, name='delete_account'),

    # Serializer JSON endpoints
    path('json/profile/', views.show_profile_json, name='show_profile_json'),
    path('json/addresses/', views.show_addresses_json, name='show_addresses_json'),

    # AJAX / API endpoints for profile, multiple addresses & RajaOngkir shipping info
    path('api/profile/', views.api_profile_data, name='api_profile_data'),
    path('api/profile/update/', views.api_update_profile, name='api_update_profile'),
    path('api/profile/preferences/', views.api_update_preferences, name='api_update_preferences'),
    path('api/addresses/add/', views.api_add_address, name='api_add_address'),
    path('api/addresses/<int:address_id>/edit/', views.api_edit_address, name='api_edit_address'),
    path('api/addresses/<int:address_id>/delete/', views.api_delete_address, name='api_delete_address'),
    path('api/addresses/<int:address_id>/set-primary/', views.api_set_primary_address, name='api_set_primary_address'),

    # AJAX / API endpoints for security (password, Google link, delete account)
    path('api/security/password/', views.api_change_password, name='api_change_password'),
    path('api/security/google/disconnect/', views.api_disconnect_google, name='api_disconnect_google'),
    path('api/security/delete-account/', views.api_delete_account, name='api_delete_account'),

    path('test/personal/', views.test_personal_access, name='test_personal_access'),
    path('test/lembaga/', views.test_lembaga_access, name='test_lembaga_access'),
]