# API Modul Marketplace & Transaksi untuk aplikasi Flutter, dibuat dengan Django REST Framework.
# Disambungkan di marketplace/urls.py dengan awalan "api/" -> /marketplace/api/...
# Filter katalog dan isi keranjang memakai fungsi yang sama dengan halaman web (views.py).
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from impact.api import CsrfExemptSessionAuthentication  # login Flutter lewat session cookie, tanpa CSRF
from marketplace.models import CartItem, Order, Product
from marketplace.templatetags.rupiah import rupiah
from marketplace.views import _cart_groups, _subtotal, filter_products


def _absolute(request, path):
    # Image.network di Flutter butuh URL lengkap, bukan "/static/..."
    return request.build_absolute_uri(path)


class ProductSerializer(serializers.ModelSerializer):
    price_label = serializers.SerializerMethodField()
    category_label = serializers.CharField(source='get_category_display')
    condition_label = serializers.CharField(source='get_condition_display')
    seller = serializers.CharField(source='seller.username')
    photo = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'price_label', 'category', 'category_label', 'condition',
                  'condition_label', 'size', 'city', 'seller', 'photo']

    def get_price_label(self, product):
        return rupiah(product.price)

    def get_photo(self, product):
        return _absolute(self.context['request'], product.photo)


class ProductDetailSerializer(ProductSerializer):
    photos = serializers.SerializerMethodField()
    in_cart = serializers.SerializerMethodField()

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ['description', 'condition_note', 'used_duration',
                                                  'weight_grams', 'photos', 'in_cart']

    def get_photos(self, product):
        return [_absolute(self.context['request'], p) for p in product.photos]

    def get_in_cart(self, product):
        user = self.context['request'].user
        return user.is_authenticated and CartItem.objects.filter(user=user, product=product).exists()


class OrderSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display')
    courier_label = serializers.CharField(source='get_courier_display')
    payment_label = serializers.CharField(source='get_payment_method_display')
    seller = serializers.CharField(source='seller.username')
    buyer = serializers.CharField(source='buyer.username')
    items = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'code', 'status', 'status_label', 'seller', 'buyer', 'courier_label', 'payment_label',
                  'subtotal', 'shipping_cost', 'total', 'created_at', 'items']

    def get_items(self, order):
        return [{'product_id': i.product_id, 'name': i.name, 'price': i.price,
                 'photo': _absolute(self.context['request'], i.photo)} for i in order.items.all()]


class OrderDetailSerializer(OrderSerializer):
    steps = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ['recipient', 'phone', 'address', 'city', 'tracking_number',
                                                'eta', 'steps']

    def get_steps(self, order):
        return order.steps()


# ---------- Katalog (boleh tanpa login) ----------

# GET /marketplace/api/katalog/?q=&kategori=&kondisi=&ukuran=&lokasi=&penjual=&min=&maks=&urut=
@api_view(['GET'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.AllowAny])
def catalog_api(request):
    products = filter_products(request.GET)
    return Response({
        'count': products.count(),
        'results': ProductSerializer(products, many=True, context={'request': request}).data,
        'categories': [{'value': v, 'label': l} for v, l in Product.CATEGORY_CHOICES],
        'conditions': [{'value': v, 'label': l} for v, l in Product.CONDITION_CHOICES],
    })


# GET /marketplace/api/katalog/<id>/ ; draf hanya terlihat oleh penjualnya (sama dengan web)
@api_view(['GET'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.AllowAny])
def product_api(request, pk):
    product = get_object_or_404(Product.objects.select_related('seller').prefetch_related('extra_photos'), pk=pk)
    if product.is_draft and product.seller != request.user:
        return Response({'detail': 'Barang ini belum tayang.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(ProductDetailSerializer(product, context={'request': request}).data)


# ---------- Keranjang (wajib login) ----------

def _cart_response(request):
    groups = _cart_groups(request.user)
    context = {'request': request}
    return {
        'count': sum(len(items) for _, items in groups),
        'subtotal': _subtotal(groups),
        'subtotal_label': rupiah(_subtotal(groups)),
        'groups': [{'seller': seller.username,
                    'items': ProductSerializer([i.product for i in items], many=True, context=context).data}
                   for seller, items in groups],
    }


# GET  /marketplace/api/keranjang/            -> isi keranjang per penjual
# POST /marketplace/api/keranjang/ {product}  -> tambah barang
@api_view(['GET', 'POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.IsAuthenticated])
def cart_api(request):
    if request.method == 'POST':
        product = get_object_or_404(Product.objects.available(), pk=request.data.get('product'))
        if product.seller == request.user:
            return Response({'detail': 'Ini barangmu sendiri.'}, status=status.HTTP_400_BAD_REQUEST)
        CartItem.objects.get_or_create(user=request.user, product=product)
        return Response(_cart_response(request), status=status.HTTP_201_CREATED)
    return Response(_cart_response(request))


# DELETE /marketplace/api/keranjang/<product_id>/
@api_view(['DELETE'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.IsAuthenticated])
def cart_item_api(request, pk):
    CartItem.objects.filter(user=request.user, product_id=pk).delete()
    return Response(_cart_response(request))


# ---------- Pesanan (wajib login) ----------

# GET /marketplace/api/pesanan/ -> pesanan yang kubeli, terbaru dulu
@api_view(['GET'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.IsAuthenticated])
def orders_api(request):
    orders = Order.objects.filter(buyer=request.user).prefetch_related('items').select_related('buyer', 'seller')
    return Response(OrderSerializer(orders, many=True, context={'request': request}).data)


# GET /marketplace/api/pesanan/<id>/ -> hanya pembeli atau penjualnya; orang lain dapat 404
@api_view(['GET'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.IsAuthenticated])
def order_api(request, pk):
    order = get_object_or_404(Order.objects.select_related('buyer', 'seller').prefetch_related('items'), pk=pk)
    if request.user not in (order.buyer, order.seller):
        return Response({'detail': 'Pesanan tidak ditemukan.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(OrderDetailSerializer(order, context={'request': request}).data)
