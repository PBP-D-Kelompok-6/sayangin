"""Integrasi RajaOngkir (Komerce API v1) untuk pencarian tujuan & perhitungan ongkir.

Tanpa RAJAONGKIR_API_KEY atau saat API gagal, jatuh dengan aman ke:
- katalog 125+ kota Indonesia lokal (sayangin.wilayah) untuk pencarian tujuan
- tarif tetap per kurir (Order.COURIER_COST) untuk ongkir
"""
import os
import re
from functools import lru_cache

import requests

from sayangin.wilayah import (
    canonical_city_name,
    format_region_name,
    normalize_city_key,
    resolve_rajaongkir_city,
    search_local_cities,
)

from .models import Order

API = 'https://rajaongkir.komerce.id/api/v1'
FLAT = Order.COURIER_COST
COURIER_LABELS = dict(Order.COURIER_CHOICES)
# JNE kadang mengembalikan CTC/CTCYES untuk pengiriman dalam kota yang sama.
SERVICE_CANDIDATES = {
    'reguler': ('REG', 'CTC', 'OKE'),
    'kilat': ('YES', 'CTCYES'),
}


def _key():
    return os.getenv('RAJAONGKIR_API_KEY', '').strip()


def _format_etd(etd_raw: str) -> str:
    if not etd_raw:
        return ''
    text = str(etd_raw).strip()
    text = re.sub(r'\bdays?\b', 'hari', text, flags=re.IGNORECASE)
    text = re.sub(r'\bhari\b', 'hari', text, flags=re.IGNORECASE)
    text = text.replace('-', '–')
    if text and 'hari' not in text.lower():
        text = f'{text} hari'
    return text


def _normalize_destination_row(row: dict) -> dict:
    raw_city = row.get('city_name') or row.get('city') or ''
    raw_province = row.get('province_name') or row.get('province') or ''
    raw_district = row.get('district_name') or row.get('district') or ''
    raw_subdistrict = row.get('subdistrict_name') or row.get('subdistrict') or ''
    zip_code = str(row.get('zip_code') or '').strip()

    city = canonical_city_name(raw_city)
    province = format_region_name(raw_province)
    district = format_region_name(raw_district)
    subdistrict = format_region_name(raw_subdistrict)

    city_id, _, resolved_prov = resolve_rajaongkir_city(city or raw_city)
    if not province and resolved_prov:
        province = resolved_prov

    parts = [p for p in (subdistrict, district, city, province) if p]
    label = ', '.join(parts) if parts else (row.get('label') or city)
    if zip_code and zip_code not in label:
        label = f'{label} ({zip_code})'

    return {
        'destination_id': str(row.get('id') or '').strip(),
        'rajaongkir_city_id': city_id,
        'label': label,
        'subdistrict': subdistrict,
        'district': district,
        'city': city,
        'province': province,
        'postal_code': zip_code,
        'source': 'rajaongkir',
    }


def search_destinations(query: str, limit: int = 15) -> dict:
    """Cari tujuan domestik (kota, kecamatan, kelurahan, atau kode pos 5 digit).

    Menggunakan RajaOngkir Komerce API bila key tersedia, lalu jatuh ke katalog kota lokal.
    """
    q = (query or '').strip()
    if len(q) < 2:
        return {'results': [], 'source': 'local'}

    if _key():
        try:
            r = requests.get(
                f'{API}/destination/domestic-destination',
                params={'search': q, 'limit': limit},
                headers={'key': _key()},
                timeout=5,
            )
            r.raise_for_status()
            rows = r.json().get('data') or []
            if rows:
                return {
                    'results': [_normalize_destination_row(row) for row in rows[:limit]],
                    'source': 'rajaongkir',
                }
        except (requests.RequestException, KeyError, ValueError, TypeError):
            pass

    return {'results': search_local_cities(q, limit=limit), 'source': 'local'}


@lru_cache(maxsize=256)
def _destination_id(city):
    r = requests.get(
        f'{API}/destination/domestic-destination',
        params={'search': city, 'limit': 20},
        headers={'key': _key()},
        timeout=5,
    )
    r.raise_for_status()
    found = r.json()['data']
    target_key = normalize_city_key(city)
    # "Depok" juga cocok dengan kecamatan Depok di Cirebon; utamakan yang nama kotanya persis sama.
    for d in found:
        cand = (d.get('city_name') or d.get('city') or '').strip()
        if cand.lower() == city.lower() or (target_key and normalize_city_key(cand) == target_key):
            return d['id']
    return found[0]['id']


@lru_cache(maxsize=256)
def _destination_id_by_postal(postal_code: str, city: str = ''):
    r = requests.get(
        f'{API}/destination/domestic-destination',
        params={'search': postal_code, 'limit': 10},
        headers={'key': _key()},
        timeout=5,
    )
    r.raise_for_status()
    found = r.json().get('data') or []
    if not found:
        raise IndexError('No destination for postal code')
    target_key = normalize_city_key(city) if city else ''
    for d in found:
        if str(d.get('zip_code') or '').strip() == postal_code:
            cand = (d.get('city_name') or d.get('city') or '').strip()
            if not target_key or normalize_city_key(cand) == target_key:
                return d['id']
    for d in found:
        if str(d.get('zip_code') or '').strip() == postal_code:
            return d['id']
    return found[0]['id']


def _resolve_destination(city: str, postal_code: str = '', destination_id: str = ''):
    dest_id_clean = str(destination_id or '').strip()
    if dest_id_clean.isdigit():
        return int(dest_id_clean)

    postal_clean = str(postal_code or '').strip()
    if len(postal_clean) == 5 and postal_clean.isdigit():
        try:
            return _destination_id_by_postal(postal_clean, city or '')
        except (requests.RequestException, KeyError, IndexError, ValueError, TypeError):
            pass

    return _destination_id(city)


def ongkir_detail(
    origin_city,
    dest_city,
    weight_grams,
    *,
    dest_postal_code='',
    dest_id='',
    origin_postal_code='',
    origin_id='',
):
    """Hitung ongkir + label layanan/ETD via RajaOngkir (fallback per kurir ke tarif flat)."""
    fallback = {
        'costs': dict(FLAT),
        'labels': dict(COURIER_LABELS),
        'source': 'flat',
    }
    if not _key():
        return fallback
    try:
        origin_dest = _resolve_destination(origin_city, origin_postal_code, origin_id)
        target_dest = _resolve_destination(dest_city, dest_postal_code, dest_id)
        r = requests.post(
            f'{API}/calculate/domestic-cost',
            headers={'key': _key()},
            timeout=5,
            data={
                'origin': origin_dest,
                'destination': target_dest,
                'weight': max(int(weight_grams or 0), 1),
                'courier': 'jne',
                'price': 'lowest',
            },
        )
        r.raise_for_status()
        rows = r.json()['data'] or []
        found = {str(row.get('service') or '').upper(): row for row in rows if 'cost' in row}
    except (requests.RequestException, KeyError, IndexError, ValueError, TypeError):
        return fallback

    costs = {}
    labels = {}
    matched_any = False
    for courier_key, candidates in SERVICE_CANDIDATES.items():
        matched_row = next((found[svc] for svc in candidates if svc in found), None)
        if matched_row is not None:
            matched_any = True
            costs[courier_key] = int(matched_row['cost'])
            svc_code = str(matched_row.get('service') or candidates[0]).upper()
            etd = _format_etd(matched_row.get('etd', ''))
            base_name = 'Reguler' if courier_key == 'reguler' else 'Kilat'
            labels[courier_key] = (
                f'{base_name} (JNE {svc_code}) · {etd}' if etd else f'{base_name} (JNE {svc_code})'
            )
        else:
            costs[courier_key] = FLAT[courier_key]
            labels[courier_key] = COURIER_LABELS[courier_key]

    return {
        'costs': costs,
        'labels': labels,
        'source': 'rajaongkir' if matched_any else 'flat',
    }


def ongkir(
    origin_city,
    dest_city,
    weight_grams,
    *,
    dest_postal_code='',
    dest_id='',
    origin_postal_code='',
    origin_id='',
):
    """{'reguler': biaya, 'kilat': biaya}; per kurir jatuh ke tarif tetap kalau tidak ada di hasil API."""
    return ongkir_detail(
        origin_city,
        dest_city,
        weight_grams,
        dest_postal_code=dest_postal_code,
        dest_id=dest_id,
        origin_postal_code=origin_postal_code,
        origin_id=origin_id,
    )['costs']
