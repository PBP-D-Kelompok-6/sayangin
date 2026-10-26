from django.urls import path

from . import views

app_name = 'marketplace'

urlpatterns = [
    path('', views.catalog, name='catalog'),
    path('barang/<int:pk>/', views.product_detail, name='detail'),
    path('barang/<int:pk>/keranjang/', views.add_to_cart, name='add_to_cart'),
    path('keranjang/', views.cart, name='cart'),
    path('keranjang/<int:pk>/hapus/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('pesanan/', views.orders, name='orders'),
    path('pesanan/<int:pk>/', views.order_detail, name='order_detail'),
]
