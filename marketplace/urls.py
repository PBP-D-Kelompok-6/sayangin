from django.urls import path

from . import api, views

app_name = 'marketplace'

urlpatterns = [
    path('', views.catalog, name='catalog'),
    path('barang/<int:pk>/', views.product_detail, name='detail'),
    path('barang/<int:pk>/keranjang/', views.add_to_cart, name='add_to_cart'),
    path('barang/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('barang/<int:pk>/hapus/', views.product_delete, name='product_delete'),
    path('barang/<int:pk>/tayang/', views.product_published, name='product_published'),
    path('jual/', views.product_create, name='product_create'),
    path('barang-saya/', views.my_products, name='my_products'),
    path('api/barang/', views.products_api, name='products_api'),
    path('foto/<path:path>', views.photo, name='photo'),
    path('keranjang/', views.cart, name='cart'),
    path('keranjang/jumlah/', views.cart_count_api, name='cart_count_api'),
    path('keranjang/<int:pk>/hapus/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/alamat/', views.checkout_address, name='checkout_address'),
    path('checkout/pengiriman/', views.checkout_shipping, name='checkout_shipping'),
    path('checkout/pembayaran/', views.checkout_payment, name='checkout_payment'),
    path('pesanan/', views.orders, name='orders'),
    path('pesanan/<int:pk>/', views.order_detail, name='order_detail'),
    # API DRF untuk aplikasi Flutter
    path('api/katalog/', api.catalog_api, name='api_catalog'),
    path('api/katalog/<int:pk>/', api.product_api, name='api_product'),
    path('api/keranjang/', api.cart_api, name='api_cart'),
    path('api/keranjang/<int:pk>/', api.cart_item_api, name='api_cart_item'),
    path('api/pesanan/', api.orders_api, name='api_orders'),
    path('api/pesanan/<int:pk>/', api.order_api, name='api_order'),
]
