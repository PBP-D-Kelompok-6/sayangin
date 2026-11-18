from django.urls import path
from rest_framework.routers import SimpleRouter

from main import api, views

app_name = 'main'

urlpatterns = [
    path('', views.show_main, name='show_main'),
    path('menu/', views.show_menu, name='show_menu'),
    path('login/', views.show_login, name='show_login'),
    path('register/', views.show_register, name='show_register'),
    path('logout/', views.logout_user, name='logout_user'),
    path('auth/google/', views.google_login, name='google_login'),
    path('auth/google/callback/', views.google_callback, name='google_callback'),
    path('auth/login/', api.auth_login_pbp, name='auth_login'),
    path('auth/logout/', api.auth_logout_pbp, name='auth_logout'),
    path('auth/register/', api.auth_register_pbp, name='auth_register'),
    path('profil/personal/', views.show_profile, name='show_profile'),
    path('profil/personal/edit/', views.edit_profile, name='edit_profile'),
    path('profil/lembaga/', views.show_lembaga_profile, name='show_lembaga_profile'),
    path('profil/lembaga/edit/', views.edit_institution_profile, name='edit_institution_profile'),
    path('profil/password/', views.change_password, name='change_password'),
    path('profil/hapus/', views.delete_account, name='delete_account'),

    # Serializer JSON endpoints (django.core.serializers)
    path('json/profile/', views.show_profile_json, name='show_profile_json'),
    path('json/addresses/', views.show_addresses_json, name='show_addresses_json'),

    # DRF Authentication endpoints
    path('api/auth/login/', api.api_login, name='api_login'),
    path('api/auth/register/', api.api_register, name='api_register'),
    path('api/auth/logout/', api.api_logout, name='api_logout'),
    path('api/auth/me/', api.api_auth_me, name='api_auth_me'),
    path('api/auth/google/', api.api_google_auth, name='api_google_auth'),

    # DRF Profile, Preferences, Addresses & RajaOngkir endpoints
    path('api/profile/', api.api_profile_data, name='api_profile_data'),
    path('api/profile/update/', api.api_update_profile, name='api_update_profile'),
    path('api/profile/preferences/', api.api_update_preferences, name='api_update_preferences'),
    path('api/addresses/add/', api.api_add_address, name='api_add_address'),
    path('api/addresses/<int:address_id>/edit/', api.api_edit_address, name='api_edit_address'),
    path('api/addresses/<int:address_id>/delete/', api.api_delete_address, name='api_delete_address'),
    path('api/addresses/<int:address_id>/set-primary/', api.api_set_primary_address, name='api_set_primary_address'),
    path('api/rajaongkir/destinations/', api.api_rajaongkir_destinations, name='api_rajaongkir_destinations'),

    # DRF Lembaga Mitra profile endpoint
    path('api/lembaga/profile/', api.api_lembaga_profile, name='api_lembaga_profile'),

    # DRF Security endpoints (password, Google link, delete account)
    path('api/security/password/', api.api_change_password, name='api_change_password'),
    path('api/security/google/disconnect/', api.api_disconnect_google, name='api_disconnect_google'),
    path('api/security/delete-account/', api.api_delete_account, name='api_delete_account'),

    path('test/personal/', views.test_personal_access, name='test_personal_access'),
    path('test/lembaga/', views.test_lembaga_access, name='test_lembaga_access'),
]

router = SimpleRouter()
router.register('api/addresses', api.UserAddressViewSet, basename='api_address')
router.register('api/lembaga', api.InstitutionPublicViewSet, basename='api_lembaga')
urlpatterns += router.urls