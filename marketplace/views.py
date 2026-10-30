from itertools import groupby
from pathlib import Path

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db.models import Count, Max, Min, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_GET, require_POST
from django.views.static import serve

from sayangin.pilihan import UKURAN_ANAK, UKURAN_BAJU

from .forms import PHOTO_TYPES, ProductForm
from .models import BULAN_PANJANG, CartItem, Order, OrderItem, Product, ProductPhoto
from .ongkir import ongkir
from .templatetags.rupiah import rupiah

# Foto upload penjual disimpan di <proyek>/media/marketplace dan disajikan lewat /marketplace/foto/<nama>.
# Sengaja tidak memakai MEDIA_ROOT bersama: nilainya BASE_DIR / '/media/' menunjuk ke /media di root disk.
PHOTOS = FileSystemStorage(location=settings.BASE_DIR / 'media' / 'marketplace', base_url='/marketplace/foto/')

def photo(request, path):
    """Sajikan foto upload penjual (juga di PWS, tempat WhiteNoise hanya melayani file static)."""
    return serve(request, path, document_root=PHOTOS.location)


SORTS = {'terbaru': '-created_at', 'termurah': 'price', 'termahal': '-price'}
ADDRESS_FIELDS = ('recipient', 'phone', 'address', 'city')

# ponytail: padanan kata sederhana (Inggris/sinonim → nama barang di katalog); ganti dengan pencarian
# yang lebih pintar kalau katalog sudah besar.
SINONIM = {
    'coat': 'mantel', 'trench': 'mantel', 'outer': 'jaket', 'jacket': 'jaket', 'jaket': 'jaket',
    'blazer': 'blazer', 'krem': 'camel', 'cream': 'camel', 'shirt': 'kemeja', 'kaos': 'kemeja',
    'sweater': 'sweter', 'cardigan': 'kardigan', 'pants': 'celana', 'jeans': 'jeans', 'skirt': 'rok',
    'shoes': 'sepatu', 'sneaker': 'sneakers', 'heels': 'heels', 'bag': 'tas', 'watch': 'jam',
    'glasses': 'kacamata', 'earring': 'anting', 'scarf': 'syal',
}


def _int_or_none(value):
    return int(value) if value and value.isdigit() else None


def _words(q):
    return [w for w in q.lower().split() if len(w) >= 3]


def _similar_by_name(q, limit=4):
    """Barang tersedia yang namanya memuat salah satu kata pencarian atau sinonimnya."""
    terms = {t for w in _words(q) for t in (w, SINONIM.get(w, w))}
    if not terms:
        return []
    match = Q()
    for t in terms:
        match |= Q(name__icontains=t)
    return list(Product.objects.available().filter(match)[:limit])


def _related_products(q, limit=4):
    """C2b "Mungkin cocok juga": padanan nama dulu, lalu barang sekategori, baru barang terbaru."""
    base = Product.objects.available()
    found = _similar_by_name(q, limit)
    if found and len(found) < limit:
        same_kind = base.filter(category__in={p.category for p in found}).exclude(pk__in=[p.pk for p in found])
        found += list(same_kind.order_by('-created_at')[:limit - len(found)])
    if len(found) < limit:
        found += list(base.exclude(pk__in=[p.pk for p in found]).order_by('-created_at')[:limit - len(found)])
    return found


def _other_keywords(q):
    """Saran "Coba kata lain": potong kata terakhir, dan versi dengan sinonim."""
    words = _words(q)
    synonym_phrase = ' '.join(dict.fromkeys(SINONIM.get(w, w) for w in words))
    options = [' '.join(words[:-1]) if len(words) > 1 else '', synonym_phrase]
    options += [SINONIM[w] for w in words if w in SINONIM]
    return [o for o in dict.fromkeys(options) if o and o != q.lower()][:3]


def catalog(request):
    products = Product.objects.available().select_related('seller')
    q = request.GET.get('q', '').strip()
    categories = request.GET.getlist('kategori')
    conditions = request.GET.getlist('kondisi')
    sizes = request.GET.getlist('ukuran')
    city = request.GET.get('lokasi', '')
    seller = request.GET.get('penjual', '')
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
    if seller:
        products = products.filter(seller__username=seller)
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
        'penjual': {seller: f'@{seller}'},
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

    # C2b: pencarian tanpa hasil → bukan jalan buntu: tawarkan kata lain + barang yang mungkin cocok.
    nothing_found = bool(q) and not products.exists()

    return render(request, 'marketplace/catalog.html', {
        'products': products,
        'nothing_found': nothing_found,
        'related': _related_products(q) if nothing_found else [],
        'other_keywords': _other_keywords(q) if nothing_found else [],
        'total_available': Product.objects.available().count(),
        'q': q,
        'searching': bool(q or active),
        'active_filters': active,
        'categories': Product.CATEGORY_CHOICES,
        'conditions': Product.CONDITION_CHOICES,
        'sizes': UKURAN_BAJU + UKURAN_ANAK,
        'cities': Product.objects.available().values_list('city', flat=True).distinct().order_by('city'),
        'selected': {'kategori': categories, 'kondisi': conditions, 'ukuran': sizes, 'lokasi': city,
                     'penjual': seller, 'min': request.GET.get('min', ''), 'maks': request.GET.get('maks', '')},
        'sort': sort,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related('seller').prefetch_related('extra_photos'), pk=pk)
    if product.is_draft and product.seller != request.user:
        raise Http404('Barang ini belum tayang.')  # draf hanya bisa dilihat penjualnya
    similar = Product.objects.available().filter(category=product.category).exclude(pk=pk)[:6]
    in_cart = request.user.is_authenticated and CartItem.objects.filter(user=request.user, product=product).exists()
    joined = product.seller.date_joined
    return render(request, 'marketplace/detail.html', {
        'product': product,
        'similar': similar,
        'in_cart': in_cart,
        'seller_sold': Product.objects.filter(seller=product.seller, is_sold=True).count(),
        'seller_joined': f'{BULAN_PANJANG[joined.month - 1]} {joined.year}',
        'shipping_from': min(Order.COURIER_COST.values()),
    })


# ---------- CRUD barang milik penjual ----------

@login_required
def my_products(request):
    items = Product.objects.filter(seller=request.user)
    return render(request, 'marketplace/my_products.html', {
        'available': items.available(), 'sold': items.filter(is_sold=True), 'drafts': items.filter(is_draft=True),
        'nav_active': 'jualanku',
        'sale_counts': _status_counts(Order.objects.filter(seller=request.user)),
        # Pesanan yang masih menunggu tombol penjual (kemas → kirim → tiba); setelah tiba giliran pembeli.
        'to_handle': Order.objects.filter(seller=request.user, status__in=['dibayar', 'dikemas', 'dikirim'])
                     .prefetch_related('items').select_related('buyer'),
    })


def _price_ranges():
    """Kisaran harga barang serupa per kategori, untuk saran harga di form jual: {'atasan': [40000, 150000]}."""
    rows = Product.objects.available().values('category').annotate(low=Min('price'), high=Max('price'))
    return {r['category']: [r['low'], r['high']] for r in rows}


def _product_form_page(request, form, product=None):
    return render(request, 'marketplace/product_form.html', {
        'form': form, 'editing': product is not None, 'product': product, 'price_ranges': _price_ranges(),
        'nav_active': 'jualanku', 'bad_fields': [field for field in form if field.errors],
    })


def _save_product(request, form):
    """Simpan barang + foto upload. Tombol "Simpan draf" menyimpan tanpa menayangkan."""
    product = form.save(commit=False)
    product.seller = request.user
    product.is_draft = request.POST.get('action') == 'draft'
    if photos := form.cleaned_data['photos']:  # foto baru menggantikan semua foto lama
        paths = [PHOTOS.url(PHOTOS.save(f'{get_random_string(16)}{PHOTO_TYPES[Path(f.name).suffix.lower()]}', f)) for f in photos]
        product.image = paths[0]
        product.save()
        product.extra_photos.all().delete()
        ProductPhoto.objects.bulk_create([ProductPhoto(product=product, image=path) for path in paths[1:]])
    else:
        product.save()
    return product


@login_required
def product_create(request):
    last = Product.objects.filter(seller=request.user).first()
    form = ProductForm(request.POST or None, request.FILES or None, initial={'city': last.city if last else ''})
    if request.method == 'POST' and form.is_valid():
        product = _save_product(request, form)
        if product.is_draft:
            messages.success(request, f'Draf {product.name} disimpan. Belum tampil di marketplace.')
            return redirect('marketplace:my_products')
        return redirect('marketplace:product_published', pk=product.pk)
    return _product_form_page(request, form)


@login_required
def product_published(request, pk):
    """Halaman sukses setelah barang dipasang (desain Figma B4 · sukses)."""
    return render(request, 'marketplace/product_published.html', {
        'product': _own_product(request, pk), 'nav_active': 'jualanku',
    })


def _own_product(request, pk):
    """Hanya penjual pemilik yang boleh mengubah/menghapus, dan hanya selama belum terjual."""
    return get_object_or_404(Product, pk=pk, seller=request.user, is_sold=False)


@login_required
def product_edit(request, pk):
    product = _own_product(request, pk)
    was_draft = product.is_draft
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        product = _save_product(request, form)
        if product.is_draft:
            messages.success(request, 'Draf disimpan.')
            return redirect('marketplace:my_products')
        if was_draft:  # draf yang baru dijual sekarang
            return redirect('marketplace:product_published', pk=pk)
        messages.success(request, 'Perubahan disimpan.')
        return redirect('marketplace:detail', pk=pk)
    return _product_form_page(request, form, product)


@login_required
@require_POST
def product_delete(request, pk):
    product = _own_product(request, pk)
    name = product.name
    product.delete()
    messages.success(request, f'{name} dihapus dari marketplace.')
    return redirect('marketplace:my_products')


# ---------- Keranjang (bisa lewat AJAX: balas JSON, tanpa memuat ulang halaman) ----------

def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _cart_count(user):
    return CartItem.objects.filter(user=user, product__is_sold=False).count()


@login_required
@require_GET
def cart_count_api(request):
    return JsonResponse({'cart_count': _cart_count(request.user)})


@login_required
@require_POST
def add_to_cart(request, pk):
    product = get_object_or_404(Product.objects.available(), pk=pk)
    if product.seller == request.user:
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'message': 'Ini barangmu sendiri.'}, status=400)
        messages.error(request, 'Ini barangmu sendiri.')
        return redirect('marketplace:detail', pk=pk)
    CartItem.objects.get_or_create(user=request.user, product=product)
    if request.POST.get('next') == 'checkout':
        return redirect('marketplace:checkout')
    message = f'{product.name} masuk keranjang.'
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'message': message, 'cart_count': _cart_count(request.user)})
    messages.success(request, message)
    return redirect('marketplace:detail', pk=pk)


@login_required
@require_POST
def remove_from_cart(request, pk):
    CartItem.objects.filter(user=request.user, product_id=pk).delete()
    if _is_ajax(request):
        groups = _cart_groups(request.user)
        return JsonResponse({'ok': True, 'cart_count': _cart_count(request.user),
                             'subtotal': rupiah(_subtotal(groups)), 'empty': not groups})
    return redirect('marketplace:cart')


# ---------- JSON: daftar barang (Read lewat JSON) ----------

def products_api(request):
    """GET /marketplace/api/barang/?q=jaket&kategori=atasan&id=3&limit=4 → barang tersedia (terbaru dulu) dalam JSON.

    Dipakai juga modul lain (mis. landing "Baru masuk") supaya harga selalu sama dengan marketplace."""
    products = Product.objects.available().select_related('seller')
    if q := request.GET.get('q', '').strip():
        products = products.filter(name__icontains=q)
    if categories := request.GET.getlist('kategori'):
        products = products.filter(category__in=categories)
    if ids := [i for i in request.GET.getlist('id') if i.isdigit()]:
        products = products.filter(pk__in=ids)
    if (limit := request.GET.get('limit', '')).isdigit():
        products = products[:int(limit)]
    products = list(products)
    return JsonResponse({'count': len(products), 'results': [{
        'id': p.pk, 'name': p.name, 'price': p.price, 'price_label': rupiah(p.price),
        'category': p.category, 'condition': p.get_condition_display(), 'size': p.size, 'city': p.city,
        'seller': p.seller.username, 'photo': request.build_absolute_uri(p.photo),
        'url': request.build_absolute_uri(reverse('marketplace:detail', args=[p.pk])),
    } for p in products]})


def _cart_groups(user):
    """Isi keranjang yang masih tersedia, dikelompokkan per penjual."""
    items = (CartItem.objects.filter(user=user, product__is_sold=False)
             .select_related('product__seller').order_by('product__seller_id', '-added_at'))
    return [(seller, list(group)) for seller, group in groupby(items, key=lambda i: i.product.seller)]


def _subtotal(groups):
    return sum(i.product.price for _, items in groups for i in items)


def _count(groups):
    return sum(len(items) for _, items in groups)


@login_required
def cart(request):
    groups = _cart_groups(request.user)
    return render(request, 'marketplace/cart.html', {'groups': groups, 'subtotal': _subtotal(groups)})


@login_required
def checkout(request):
    """Pintu masuk: lanjut ke langkah pertama yang belum lengkap."""
    if 'checkout_address' in request.session:
        return redirect('marketplace:checkout_shipping')
    return redirect('marketplace:checkout_address')


@login_required
def checkout_address(request):
    groups = _cart_groups(request.user)
    if not groups:
        messages.error(request, 'Keranjangmu kosong.')
        return redirect('marketplace:catalog')

    # Isi otomatis dari sesi atau alamat pesanan terakhir, supaya tidak mengetik ulang.
    last = Order.objects.filter(buyer=request.user).first()
    initial = request.session.get('checkout_address') or (
        {f: getattr(last, f) for f in ADDRESS_FIELDS} if last else {'recipient': request.user.get_full_name()})
    form, errors = initial, {}
    if request.method == 'POST':
        form = {f: request.POST.get(f, '').strip() for f in ADDRESS_FIELDS}
        errors = {f: 'Wajib diisi.' for f, v in form.items() if not v}
        if not errors:
            request.session['checkout_address'] = form
            return redirect('marketplace:checkout_shipping')
    return render(request, 'marketplace/checkout_address.html', {
        'step': 1, 'form': form, 'errors': errors,
        'groups': groups, 'subtotal': _subtotal(groups), 'count': _count(groups), 'shipping': 0,
    })


@login_required
def checkout_shipping(request):
    groups = _cart_groups(request.user)
    address = request.session.get('checkout_address')
    if not groups:
        return redirect('marketplace:cart')
    if not address:
        return redirect('marketplace:checkout_address')

    # Ongkir per penjual: dari kota penjual ke kota pembeli, sesuai total berat barangnya.
    costs = {str(s.pk): ongkir(items[0].product.city, address['city'], sum(i.product.weight_grams for i in items))
             for s, items in groups}
    chosen = request.session.get('checkout_couriers', {})
    errors = {}
    if request.method == 'POST':
        chosen = {str(s.pk): request.POST.get(f'courier_{s.pk}') for s, _ in groups}
        errors = {k: 'Pilih kurir untuk penjual ini dulu.' for k, v in chosen.items() if v not in Order.COURIER_COST}
        if not errors:
            request.session['checkout_couriers'] = chosen
            request.session['checkout_costs'] = costs
            return redirect('marketplace:checkout_payment')

    shipping = sum(costs[k].get(chosen.get(k), 0) for k in costs)
    return render(request, 'marketplace/checkout_shipping.html', {
        'step': 2, 'address': address,
        'groups': [{'seller': s, 'items': items, 'courier': chosen.get(str(s.pk)), 'error': errors.get(str(s.pk)),
                    'couriers': [(key, label, costs[str(s.pk)][key]) for key, label in Order.COURIER_CHOICES]}
                   for s, items in groups],
        'subtotal': _subtotal(groups), 'count': _count(groups), 'shipping': shipping,
    })


@login_required
def checkout_payment(request):
    groups = _cart_groups(request.user)
    address = request.session.get('checkout_address')
    couriers = request.session.get('checkout_couriers', {})
    if not groups:
        return redirect('marketplace:cart')
    if not address:
        return redirect('marketplace:checkout_address')
    if any(couriers.get(str(s.pk)) not in Order.COURIER_COST for s, _ in groups):
        return redirect('marketplace:checkout_shipping')

    saved = request.session.get('checkout_costs', {})
    cost = {str(s.pk): saved.get(str(s.pk), Order.COURIER_COST)[couriers[str(s.pk)]] for s, _ in groups}
    error = None
    if request.method == 'POST':
        payment = request.POST.get('payment')
        if payment not in dict(Order.PAYMENT_CHOICES):
            error = 'Pilih metode pembayaran.'
        else:
            with transaction.atomic():
                orders = []
                for seller, items in groups:
                    courier = couriers[str(seller.pk)]
                    order = Order(buyer=request.user, seller=seller, courier=courier,
                                  shipping_cost=cost[str(seller.pk)], payment_method=payment, **address)
                    order.set_status('dibayar')
                    order.save()
                    OrderItem.objects.bulk_create([
                        OrderItem(order=order, product=i.product, name=i.product.name,
                                  price=i.product.price, image=i.product.image) for i in items])
                    Product.objects.filter(pk__in=[i.product_id for i in items]).update(is_sold=True)
                    orders.append(order)
                CartItem.objects.filter(user=request.user).delete()
            request.session.pop('checkout_couriers', None)
            request.session.pop('checkout_costs', None)
            messages.success(request, 'Pembayaran diterima. Terima kasih sudah memilih preloved!')
            if len(orders) == 1:
                return redirect('marketplace:order_detail', pk=orders[0].pk)
            return redirect('marketplace:orders')

    labels = dict(Order.COURIER_CHOICES)
    return render(request, 'marketplace/checkout_payment.html', {
        'step': 3, 'address': address, 'error': error,
        'groups': [{'seller': s, 'items': items, 'courier': labels[couriers[str(s.pk)]],
                    'cost': cost[str(s.pk)]} for s, items in groups],
        'payments': Order.PAYMENT_CHOICES,
        'subtotal': _subtotal(groups), 'count': _count(groups),
        'shipping': sum(cost.values()),
    })


def _status_counts(orders):
    """Jumlah pesanan per status, seperti tab Shopee: [('Dibayar', 1), ('Dikemas', 0), ...]."""
    counts = dict(orders.values_list('status').annotate(n=Count('pk')).order_by())
    return [(Order.STATUS_SHORT[key], counts.get(key, 0)) for key, _ in Order.STATUS_CHOICES]


@login_required
def orders(request):
    my_orders = Order.objects.filter(buyer=request.user).prefetch_related('items').select_related('seller')
    return render(request, 'marketplace/orders.html', {
        'orders': my_orders,
        'bought_count': OrderItem.objects.filter(order__buyer=request.user).count(),
        'order_counts': _status_counts(my_orders),
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
            order.set_status(keys[order.status_index + 1])
            if order.status == 'dikirim':
                order.tracking_number = 'JNE' + get_random_string(10, '0123456789')
            order.save()
        elif action == 'confirm' and is_buyer and order.status == 'tiba':
            order.set_status('selesai')
            order.save()
        return redirect('marketplace:order_detail', pk=pk)

    next_label = None
    if is_seller and order.status in ('dibayar', 'dikemas', 'dikirim'):
        next_label = {'dibayar': 'Tandai dikemas', 'dikemas': 'Tandai dikirim', 'dikirim': 'Tandai tiba'}[order.status]
    title, emphasis = Order.STATUS_TITLE[order.status]
    return render(request, 'marketplace/order_detail.html', {
        'order': order, 'steps': order.steps(), 'is_buyer': is_buyer, 'next_label': next_label,
        'title': title, 'emphasis': emphasis, 'short_status': Order.STATUS_SHORT[order.status],
    })
