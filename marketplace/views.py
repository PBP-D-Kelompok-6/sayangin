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

from main.models import UserAddress, UserProfile
from sayangin.pilihan import UKURAN_ANAK, UKURAN_BAJU
from sayangin.wilayah import get_city_groups

from .forms import PHOTO_TYPES, ProductForm
from .models import BULAN_PANJANG, CartItem, Order, OrderItem, Product, ProductPhoto
from .ongkir import ongkir, ongkir_detail
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
    initial_city = last.city if last else ''
    if not initial_city:
        primary_addr = UserAddress.objects.filter(user=request.user).first()
        if primary_addr and primary_addr.city:
            initial_city = primary_addr.city
        else:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            initial_city = profile.city or ''
    form = ProductForm(request.POST or None, request.FILES or None, initial={'city': initial_city})
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


def _user_saved_addresses(user):
    """Ambil semua UserAddress milik user; sinkronkan dulu bila masih ada alamat lama di UserProfile."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not UserAddress.objects.filter(user=user).exists() and (profile.address.strip() or profile.city.strip()):
        UserAddress.objects.create(
            user=user,
            label=profile.address_label or 'RUMAH',
            recipient_name=profile.full_name,
            phone_number=profile.phone_number,
            address=profile.address,
            city=profile.city,
            postal_code=profile.postal_code,
            is_primary=True,
        )
    return profile, list(UserAddress.objects.filter(user=user))


def _address_to_checkout_dict(addr, user, profile):
    return {
        'address_id': addr.pk,
        'label': addr.label,
        'label_display': addr.get_label_display(),
        'recipient': (addr.recipient_name or profile.full_name or user.get_full_name() or user.username).strip(),
        'phone': (addr.phone_number or profile.phone_number or '').strip(),
        'address': addr.address.strip(),
        'subdistrict': addr.subdistrict.strip(),
        'district': addr.district.strip(),
        'city': addr.city.strip(),
        'province': addr.province.strip(),
        'postal_code': addr.postal_code.strip(),
        'rajaongkir_city_id': addr.rajaongkir_city_id.strip(),
        'rajaongkir_destination_id': addr.rajaongkir_destination_id.strip(),
    }


def _resolve_active_checkout_address(request):
    """Segarkan alamat checkout dari UserAddress bila terhubung ke profil agar perubahan langsung ikut."""
    address = request.session.get('checkout_address')
    if not address:
        return None
    addr_id = address.get('address_id')
    if addr_id:
        addr = UserAddress.objects.filter(user=request.user, pk=addr_id).first()
        if addr:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            refreshed = _address_to_checkout_dict(addr, request.user, profile)
            if not refreshed['phone'] and address.get('phone'):
                refreshed['phone'] = address['phone']
            request.session['checkout_address'] = refreshed
            return refreshed
    return address


def _clear_checkout_shipping_session(request):
    request.session.pop('checkout_couriers', None)
    request.session.pop('checkout_costs', None)
    request.session.pop('checkout_courier_labels', None)


def _seller_origin_info(seller, product_city):
    """Cocokkan kota produk penjual dengan alamat profil penjual untuk ID/kode pos RajaOngkir."""
    city_low = (product_city or '').strip().lower()
    if not city_low:
        return '', ''
    for addr in UserAddress.objects.filter(user=seller):
        if addr.city.strip().lower() == city_low:
            return addr.postal_code.strip(), addr.rajaongkir_destination_id.strip()
    return '', ''


@login_required
def checkout(request):
    """Pintu masuk: lanjut ke langkah pertama yang belum lengkap."""
    active = _resolve_active_checkout_address(request)
    if active and all(active.get(f) for f in ADDRESS_FIELDS):
        return redirect('marketplace:checkout_shipping')
    return redirect('marketplace:checkout_address')


@login_required
def checkout_address(request):
    groups = _cart_groups(request.user)
    if not groups:
        messages.error(request, 'Keranjangmu kosong.')
        return redirect('marketplace:catalog')

    profile, saved_addresses = _user_saved_addresses(request.user)
    session_addr = _resolve_active_checkout_address(request) or {}

    address_cards = []
    for addr in saved_addresses:
        recipient = (addr.recipient_name or profile.full_name or request.user.get_full_name() or request.user.username).strip()
        phone = (addr.phone_number or profile.phone_number or '').strip()
        address_cards.append({
            'obj': addr,
            'id': addr.pk,
            'label': addr.label,
            'label_display': addr.get_label_display(),
            'is_primary': addr.is_primary,
            'recipient': recipient,
            'phone': phone,
            'has_phone': bool(phone),
            'formatted_address': addr.formatted_address,
            'city': addr.city,
            'province': addr.province,
            'postal_code': addr.postal_code,
            'rajaongkir_city_id': addr.rajaongkir_city_id,
            'rajaongkir_destination_id': addr.rajaongkir_destination_id,
        })

    requested_addr_id = (request.POST.get('selected_address_id') or request.GET.get('address_id') or '').strip()
    saved_ids = {c['id'] for c in address_cards}
    selected_address_id = None
    if requested_addr_id.isdigit() and int(requested_addr_id) in saved_ids:
        selected_address_id = int(requested_addr_id)
    elif session_addr.get('address_id') in saved_ids:
        selected_address_id = session_addr['address_id']
    elif address_cards:
        selected_address_id = address_cards[0]['id']

    # Fallback form bila user belum punya alamat tersimpan di profil.
    last = Order.objects.filter(buyer=request.user).first()
    initial = {
        'label': session_addr.get('label') or 'RUMAH',
        'recipient': session_addr.get('recipient') or profile.full_name or (last.recipient if last else '') or request.user.get_full_name(),
        'phone': session_addr.get('phone') or profile.phone_number or (last.phone if last else ''),
        'address': session_addr.get('address') or (last.address if last else ''),
        'city': session_addr.get('city') or (last.city if last else ''),
        'postal_code': session_addr.get('postal_code') or (last.postal_code if last else ''),
        'province': session_addr.get('province', ''),
        'district': session_addr.get('district', ''),
        'subdistrict': session_addr.get('subdistrict', ''),
        'rajaongkir_destination_id': session_addr.get('rajaongkir_destination_id', ''),
    }
    form, errors = initial, {}
    phone_fallback = ''

    if request.method == 'POST':
        chosen_id = (request.POST.get('selected_address_id') or '').strip()
        if chosen_id:
            addr = UserAddress.objects.filter(user=request.user, pk=chosen_id).first() if chosen_id.isdigit() else None
            if not addr:
                errors['selected_address_id'] = 'Pilih alamat dari profilmu terlebih dahulu.'
            else:
                selected_address_id = addr.pk
                checkout_data = _address_to_checkout_dict(addr, request.user, profile)
                phone_fallback = request.POST.get('phone_fallback', '').strip()
                if not checkout_data['phone']:
                    if phone_fallback:
                        addr.phone_number = phone_fallback
                        addr.save(update_fields=['phone_number', 'updated_at'])
                        if not profile.phone_number.strip():
                            profile.phone_number = phone_fallback
                            profile.save(update_fields=['phone_number'])
                        checkout_data['phone'] = phone_fallback
                    else:
                        errors['phone_fallback'] = 'Isi nomor HP penerima supaya kurir bisa menghubungimu.'
                if not errors:
                    request.session['checkout_address'] = checkout_data
                    _clear_checkout_shipping_session(request)
                    return redirect('marketplace:checkout_shipping')
        else:
            form = {
                'label': (request.POST.get('label') or 'RUMAH').strip().upper(),
                'recipient': request.POST.get('recipient', '').strip(),
                'phone': request.POST.get('phone', '').strip(),
                'address': request.POST.get('address', '').strip(),
                'city': request.POST.get('city', '').strip(),
                'postal_code': request.POST.get('postal_code', '').strip(),
                'province': request.POST.get('province', '').strip(),
                'district': request.POST.get('district', '').strip(),
                'subdistrict': request.POST.get('subdistrict', '').strip(),
                'rajaongkir_destination_id': request.POST.get('rajaongkir_destination_id', '').strip(),
            }
            if form['label'] not in dict(UserAddress.ADDRESS_LABEL_CHOICES):
                form['label'] = 'RUMAH'
            errors = {f: 'Wajib diisi.' for f in ADDRESS_FIELDS if not form[f]}
            if not errors:
                # Simpan otomatis ke profil user agar tidak perlu mengetik ulang di transaksi berikutnya.
                new_addr = UserAddress.objects.create(
                    user=request.user,
                    label=form['label'],
                    recipient_name=form['recipient'],
                    phone_number=form['phone'],
                    address=form['address'],
                    subdistrict=form['subdistrict'],
                    district=form['district'],
                    city=form['city'],
                    province=form['province'],
                    rajaongkir_destination_id=form['rajaongkir_destination_id'],
                    postal_code=form['postal_code'],
                    is_primary=not saved_addresses,
                )
                profile_updates = []
                if not profile.full_name.strip():
                    profile.full_name = form['recipient']
                    profile_updates.append('full_name')
                if not profile.phone_number.strip():
                    profile.phone_number = form['phone']
                    profile_updates.append('phone_number')
                if profile_updates:
                    profile.save(update_fields=profile_updates)

                request.session['checkout_address'] = _address_to_checkout_dict(new_addr, request.user, profile)
                _clear_checkout_shipping_session(request)
                return redirect('marketplace:checkout_shipping')

    checkout_url = reverse('marketplace:checkout_address')
    profile_url = reverse('main:show_profile')
    return render(request, 'marketplace/checkout_address.html', {
        'step': 1,
        'form': form,
        'errors': errors,
        'phone_fallback': phone_fallback,
        'saved_addresses': address_cards,
        'selected_address_id': selected_address_id,
        'profile_add_address_url': f'{profile_url}?add_address=1&next={checkout_url}',
        'profile_manage_url': f'{profile_url}?next={checkout_url}',
        'address_label_choices': UserProfile.ADDRESS_LABEL_CHOICES,
        'city_groups': get_city_groups(),
        'groups': groups,
        'subtotal': _subtotal(groups),
        'count': _count(groups),
        'shipping': 0,
    })


@login_required
def checkout_shipping(request):
    groups = _cart_groups(request.user)
    address = _resolve_active_checkout_address(request)
    if not groups:
        return redirect('marketplace:cart')
    if not address or not all(address.get(f) for f in ADDRESS_FIELDS):
        return redirect('marketplace:checkout_address')

    # Ongkir per penjual via RajaOngkir (memanfaatkan kode pos / destination ID profil bila tersedia).
    details = {}
    weights = {}
    for s, items in groups:
        weight_grams = sum(i.product.weight_grams for i in items)
        weights[str(s.pk)] = weight_grams
        origin_postal, origin_id = _seller_origin_info(s, items[0].product.city)
        details[str(s.pk)] = ongkir_detail(
            items[0].product.city,
            address['city'],
            weight_grams,
            dest_postal_code=address.get('postal_code', ''),
            dest_id=address.get('rajaongkir_destination_id', ''),
            origin_postal_code=origin_postal,
            origin_id=origin_id,
        )

    costs = {k: d['costs'] for k, d in details.items()}
    courier_labels = {k: d['labels'] for k, d in details.items()}
    chosen = request.session.get('checkout_couriers', {})
    errors = {}
    if request.method == 'POST':
        chosen = {str(s.pk): request.POST.get(f'courier_{s.pk}') for s, _ in groups}
        errors = {k: 'Pilih kurir untuk penjual ini dulu.' for k, v in chosen.items() if v not in Order.COURIER_COST}
        if not errors:
            request.session['checkout_couriers'] = chosen
            request.session['checkout_costs'] = costs
            request.session['checkout_courier_labels'] = courier_labels
            return redirect('marketplace:checkout_payment')

    shipping = sum(costs[k].get(chosen.get(k), 0) for k in costs)
    return render(request, 'marketplace/checkout_shipping.html', {
        'step': 2,
        'address': address,
        'groups': [{
            'seller': s,
            'items': items,
            'weight_grams': weights[str(s.pk)],
            'shipping_source': details[str(s.pk)]['source'],
            'courier': chosen.get(str(s.pk)),
            'error': errors.get(str(s.pk)),
            'couriers': [
                (key, courier_labels[str(s.pk)].get(key, label), costs[str(s.pk)][key])
                for key, label in Order.COURIER_CHOICES
            ],
        } for s, items in groups],
        'subtotal': _subtotal(groups),
        'count': _count(groups),
        'shipping': shipping,
    })


@login_required
def checkout_payment(request):
    groups = _cart_groups(request.user)
    address = _resolve_active_checkout_address(request)
    couriers = request.session.get('checkout_couriers', {})
    if not groups:
        return redirect('marketplace:cart')
    if not address or not all(address.get(f) for f in ADDRESS_FIELDS):
        return redirect('marketplace:checkout_address')
    if any(couriers.get(str(s.pk)) not in Order.COURIER_COST for s, _ in groups):
        return redirect('marketplace:checkout_shipping')

    saved = request.session.get('checkout_costs', {})
    saved_labels = request.session.get('checkout_courier_labels', {})
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
                    order = Order(
                        buyer=request.user,
                        seller=seller,
                        courier=courier,
                        shipping_cost=cost[str(seller.pk)],
                        payment_method=payment,
                        recipient=address['recipient'],
                        phone=address['phone'],
                        address_label=address.get('label_display') or address.get('label') or '',
                        address=address['address'],
                        city=address['city'],
                        postal_code=address.get('postal_code', ''),
                    )
                    order.set_status('dibayar')
                    order.save()
                    OrderItem.objects.bulk_create([
                        OrderItem(order=order, product=i.product, name=i.product.name,
                                  price=i.product.price, image=i.product.image) for i in items])
                    Product.objects.filter(pk__in=[i.product_id for i in items]).update(is_sold=True)
                    orders.append(order)
                CartItem.objects.filter(user=request.user).delete()
            _clear_checkout_shipping_session(request)
            messages.success(request, 'Pembayaran diterima. Terima kasih sudah memilih preloved!')
            if len(orders) == 1:
                return redirect('marketplace:order_detail', pk=orders[0].pk)
            return redirect('marketplace:orders')

    default_labels = dict(Order.COURIER_CHOICES)
    return render(request, 'marketplace/checkout_payment.html', {
        'step': 3,
        'address': address,
        'error': error,
        'groups': [{
            'seller': s,
            'items': items,
            'courier': saved_labels.get(str(s.pk), default_labels).get(
                couriers[str(s.pk)], default_labels[couriers[str(s.pk)]]
            ),
            'cost': cost[str(s.pk)],
        } for s, items in groups],
        'payments': Order.PAYMENT_CHOICES,
        'subtotal': _subtotal(groups),
        'count': _count(groups),
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
