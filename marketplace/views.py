from itertools import groupby

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_POST

from .models import CartItem, Order, OrderItem, Product

SORTS = {'terbaru': '-created_at', 'termurah': 'price', 'termahal': '-price'}


def _int_or_none(value):
    return int(value) if value and value.isdigit() else None


def catalog(request):
    products = Product.objects.filter(is_sold=False).select_related('seller')
    q = request.GET.get('q', '').strip()
    categories = request.GET.getlist('kategori')
    conditions = request.GET.getlist('kondisi')
    sizes = request.GET.getlist('ukuran')
    city = request.GET.get('lokasi', '')
    price_min = _int_or_none(request.GET.get('min'))
    price_max = _int_or_none(request.GET.get('maks'))
    sort = request.GET.get('urut', 'terbaru')

    if q:
        products = products.filter(name__icontains=q)
    if categories:
        products = products.filter(category__in=categories)
    if conditions:
        products = products.filter(condition__in=conditions)
    if sizes:
        products = products.filter(size__in=sizes)
    if city:
        products = products.filter(city=city)
    if price_min is not None:
        products = products.filter(price__gte=price_min)
    if price_max is not None:
        products = products.filter(price__lte=price_max)
    products = products.order_by(SORTS.get(sort, '-created_at'))

    # Gelembung filter aktif: tiap gelembung adalah link yang membuang satu nilai.
    labels = {
        'kategori': dict(Product.CATEGORY_CHOICES),
        'kondisi': dict(Product.CONDITION_CHOICES),
        'ukuran': {s: f'Ukuran {s}' for s in sizes},
        'lokasi': {city: city},
        'min': {request.GET.get('min'): f'Min {request.GET.get("min")}'},
        'maks': {request.GET.get('maks'): f'Maks {request.GET.get("maks")}'},
    }
    active = []
    for key, names in labels.items():
        for value in request.GET.getlist(key):
            if not value:
                continue
            rest = request.GET.copy()
            rest.setlist(key, [v for v in rest.getlist(key) if v != value])
            active.append({'label': names.get(value, value), 'url': '?' + rest.urlencode()})

    return render(request, 'marketplace/catalog.html', {
        'products': products,
        'q': q,
        'searching': bool(q or active),
        'active_filters': active,
        'categories': Product.CATEGORY_CHOICES,
        'conditions': Product.CONDITION_CHOICES,
        'sizes': ['S', 'M', 'L', 'XL'],
        'cities': Product.objects.filter(is_sold=False).values_list('city', flat=True).distinct().order_by('city'),
        'selected': {'kategori': categories, 'kondisi': conditions, 'ukuran': sizes,
                     'lokasi': city, 'min': request.GET.get('min', ''), 'maks': request.GET.get('maks', '')},
        'sort': sort,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related('seller'), pk=pk)
    similar = Product.objects.filter(category=product.category, is_sold=False).exclude(pk=pk)[:6]
    in_cart = request.user.is_authenticated and CartItem.objects.filter(user=request.user, product=product).exists()
    return render(request, 'marketplace/detail.html', {
        'product': product,
        'similar': similar,
        'in_cart': in_cart,
        'shipping_from': min(Order.COURIER_COST.values()),
    })


@login_required
@require_POST
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk, is_sold=False)
    if product.seller == request.user:
        messages.error(request, 'Ini barangmu sendiri.')
        return redirect('marketplace:detail', pk=pk)
    CartItem.objects.get_or_create(user=request.user, product=product)
    if request.POST.get('next') == 'checkout':
        return redirect('marketplace:checkout')
    messages.success(request, f'{product.name} masuk keranjang.')
    return redirect('marketplace:detail', pk=pk)


@login_required
@require_POST
def remove_from_cart(request, pk):
    CartItem.objects.filter(user=request.user, product_id=pk).delete()
    return redirect('marketplace:cart')


def _cart_groups(user):
    """Isi keranjang yang masih tersedia, dikelompokkan per penjual."""
    items = (CartItem.objects.filter(user=user, product__is_sold=False)
             .select_related('product__seller').order_by('product__seller_id', '-added_at'))
    return [(seller, list(group)) for seller, group in groupby(items, key=lambda i: i.product.seller)]


@login_required
def cart(request):
    groups = _cart_groups(request.user)
    subtotal = sum(i.product.price for _, items in groups for i in items)
    return render(request, 'marketplace/cart.html', {'groups': groups, 'subtotal': subtotal})


@login_required
def checkout(request):
    groups = _cart_groups(request.user)
    if not groups:
        messages.error(request, 'Keranjangmu kosong.')
        return redirect('marketplace:catalog')

    form = request.POST
    errors = {}
    if request.method == 'POST':
        for field in ('recipient', 'phone', 'address', 'city'):
            if not form.get(field, '').strip():
                errors[field] = 'Wajib diisi.'
        for seller, _ in groups:
            if form.get(f'courier_{seller.pk}') not in Order.COURIER_COST:
                errors[f'courier_{seller.pk}'] = 'Pilih kurir untuk penjual ini dulu.'
        if form.get('payment') not in dict(Order.PAYMENT_CHOICES):
            errors['payment'] = 'Pilih metode pembayaran.'

        if not errors:
            with transaction.atomic():
                orders = []
                for seller, items in groups:
                    courier = form[f'courier_{seller.pk}']
                    order = Order.objects.create(
                        buyer=request.user, seller=seller,
                        recipient=form['recipient'].strip(), phone=form['phone'].strip(),
                        address=form['address'].strip(), city=form['city'].strip(),
                        courier=courier, shipping_cost=Order.COURIER_COST[courier],
                        payment_method=form['payment'],
                    )
                    for item in items:
                        p = item.product
                        OrderItem.objects.create(order=order, product=p, name=p.name, price=p.price, image=p.image)
                    Product.objects.filter(pk__in=[i.product_id for i in items]).update(is_sold=True)
                    orders.append(order)
                CartItem.objects.filter(user=request.user).delete()
            messages.success(request, 'Pembayaran diterima. Terima kasih sudah memilih preloved!')
            if len(orders) == 1:
                return redirect('marketplace:order_detail', pk=orders[0].pk)
            return redirect('marketplace:orders')

    return render(request, 'marketplace/checkout.html', {
        'groups': [{'seller': seller, 'items': items,
                    'courier': form.get(f'courier_{seller.pk}'),
                    'error': errors.get(f'courier_{seller.pk}')} for seller, items in groups],
        'subtotal': sum(i.product.price for _, items in groups for i in items),
        'couriers': [(key, label, Order.COURIER_COST[key]) for key, label in Order.COURIER_CHOICES],
        'payments': Order.PAYMENT_CHOICES,
        'form': form,
        'errors': errors,
    })


@login_required
def orders(request):
    return render(request, 'marketplace/orders.html', {
        'orders': Order.objects.filter(buyer=request.user).prefetch_related('items').select_related('seller'),
        'sales': Order.objects.filter(seller=request.user).prefetch_related('items').select_related('buyer'),
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related('buyer', 'seller'), pk=pk)
    is_buyer, is_seller = order.buyer == request.user, order.seller == request.user
    if not (is_buyer or is_seller):
        return redirect('marketplace:orders')

    if request.method == 'POST':
        action = request.POST.get('action')
        keys = [key for key, _ in Order.STATUS_CHOICES]
        if action == 'advance' and is_seller and order.status in ('dibayar', 'dikemas', 'dikirim'):
            order.status = keys[order.status_index + 1]
            if order.status == 'dikirim':
                order.tracking_number = 'JNE' + get_random_string(10, '0123456789')
            order.save()
        elif action == 'confirm' and is_buyer and order.status == 'tiba':
            order.status = 'selesai'
            order.save()
        return redirect('marketplace:order_detail', pk=pk)

    steps = [{'label': label, 'done': i < order.status_index, 'now': i == order.status_index}
             for i, (_, label) in enumerate(Order.STATUS_CHOICES)]
    next_label = None
    if is_seller and order.status in ('dibayar', 'dikemas', 'dikirim'):
        next_label = {'dibayar': 'Tandai dikemas', 'dikemas': 'Tandai dikirim', 'dikirim': 'Tandai tiba'}[order.status]
    return render(request, 'marketplace/order_detail.html', {
        'order': order, 'steps': steps, 'is_buyer': is_buyer, 'next_label': next_label,
    })
