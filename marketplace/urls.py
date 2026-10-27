from django.urls import path

from . import views

app_name = 'marketplace'

urlpatterns = [
    path('', views.catalog, name='catalog'),
    path('barang/<int:pk>/', views.product_detail, name='detail'),
    path('barang/<int:pk>/keranjang/', views.add_to_cart, name='add_to_cart'),
    path('barang/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('barang/<int:pk>/hapus/', views.product_delete, name='product_delete'),
    path('jual/', views.product_create, name='product_create'),
    path('barang-saya/', views.my_products, name='my_products'),
    path('api/barang/', views.products_api, name='products_api'),
    path('keranjang/', views.cart, name='cart'),
    path('keranjang/<int:pk>/hapus/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/alamat/', views.checkout_address, name='checkout_address'),
    path('checkout/pengiriman/', views.checkout_shipping, name='checkout_shipping'),
    path('checkout/pembayaran/', views.checkout_payment, name='checkout_payment'),
    path('pesanan/', views.orders, name='orders'),
    path('pesanan/<int:pk>/', views.order_detail, name='order_detail'),
]
