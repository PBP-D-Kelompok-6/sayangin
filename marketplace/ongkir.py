"""Ongkir dari RajaOngkir (Komerce). Tanpa API key atau saat API gagal, pakai tarif tetap per kurir."""
import os
from functools import lru_cache

import requests

from .models import Order

API = 'https://rajaongkir.komerce.id/api/v1'
FLAT = Order.COURIER_COST
SERVICE = {'reguler': 'REG', 'kilat': 'YES'}  # layanan JNE untuk tiap pilihan kurir


def _key():
    return os.getenv('RAJAONGKIR_API_KEY', '')


@lru_cache(maxsize=256)
def _destination_id(city):
    r = requests.get(f'{API}/destination/domestic-destination', params={'search': city, 'limit': 20},
                     headers={'key': _key()}, timeout=5)
    r.raise_for_status()
    found = r.json()['data']
    # "Depok" juga cocok dengan kecamatan Depok di Cirebon; utamakan yang nama kotanya persis sama.
    return next((d['id'] for d in found if d['city_name'].lower() == city.lower()), found[0]['id'])


def ongkir(origin_city, dest_city, weight_grams):
    """{'reguler': biaya, 'kilat': biaya}; per kurir jatuh ke tarif tetap kalau tidak ada di hasil API."""
    if not _key():
        return dict(FLAT)
    try:
        r = requests.post(f'{API}/calculate/domestic-cost', headers={'key': _key()}, timeout=5, data={
            'origin': _destination_id(origin_city), 'destination': _destination_id(dest_city),
            'weight': max(weight_grams, 1), 'courier': 'jne', 'price': 'lowest'})
        r.raise_for_status()
        found = {row['service']: row['cost'] for row in r.json()['data']}
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return dict(FLAT)
    return {c: found.get(s, FLAT[c]) for c, s in SERVICE.items()}
