"""Katalog kota/kabupaten Indonesia, kode pos contoh, dan pemetaan RajaOngkir.

Dipakai bersama oleh modul main (profil & alamat), marketplace (checkout & ongkir),
dan lemari (kota pengiriman) agar semua modul konsisten.
"""
import re

# (nama_kota, rajaongkir_city_id, rajaongkir_province_id, nama_provinsi, kode_pos_contoh)
# ID kota & provinsi mengikuti standar RajaOngkir (mempertahankan 19 kota awal + perluasan seluruh Indonesia).
INDONESIAN_CITIES = [
    # DKI Jakarta
    ("Jakarta Pusat", "152", "6", "DKI Jakarta", "10110"),
    ("Jakarta Selatan", "153", "6", "DKI Jakarta", "12110"),
    ("Jakarta Barat", "151", "6", "DKI Jakarta", "11110"),
    ("Jakarta Timur", "154", "6", "DKI Jakarta", "13110"),
    ("Jakarta Utara", "155", "6", "DKI Jakarta", "14110"),
    ("Kepulauan Seribu", "189", "6", "DKI Jakarta", "14510"),
    # Banten
    ("Tangerang", "456", "3", "Banten", "15111"),
    ("Kab. Tangerang", "455", "3", "Banten", "15710"),
    ("Tangerang Selatan", "457", "3", "Banten", "15310"),
    ("Serang", "403", "3", "Banten", "42111"),
    ("Kab. Serang", "402", "3", "Banten", "42182"),
    ("Cilegon", "106", "3", "Banten", "42411"),
    ("Lebak", "232", "3", "Banten", "42311"),
    ("Pandeglang", "331", "3", "Banten", "42211"),
    # Jawa Barat
    ("Depok", "115", "9", "Jawa Barat", "16411"),
    ("Bogor", "79", "9", "Jawa Barat", "16111"),
    ("Kab. Bogor", "78", "9", "Jawa Barat", "16911"),
    ("Bekasi", "55", "9", "Jawa Barat", "17111"),
    ("Kab. Bekasi", "54", "9", "Jawa Barat", "17510"),
    ("Bandung", "23", "9", "Jawa Barat", "40111"),
    ("Kab. Bandung", "22", "9", "Jawa Barat", "40911"),
    ("Bandung Barat", "24", "9", "Jawa Barat", "40552"),
    ("Cimahi", "107", "9", "Jawa Barat", "40511"),
    ("Cirebon", "109", "9", "Jawa Barat", "45111"),
    ("Kab. Cirebon", "108", "9", "Jawa Barat", "45611"),
    ("Sukabumi", "431", "9", "Jawa Barat", "43111"),
    ("Tasikmalaya", "469", "9", "Jawa Barat", "46111"),
    ("Garut", "126", "9", "Jawa Barat", "44111"),
    ("Karawang", "171", "9", "Jawa Barat", "41311"),
    ("Purwakarta", "376", "9", "Jawa Barat", "41111"),
    ("Subang", "428", "9", "Jawa Barat", "41211"),
    ("Sumedang", "440", "9", "Jawa Barat", "45311"),
    ("Indramayu", "149", "9", "Jawa Barat", "45211"),
    ("Cianjur", "103", "9", "Jawa Barat", "43211"),
    ("Kuningan", "211", "9", "Jawa Barat", "45511"),
    ("Majalengka", "252", "9", "Jawa Barat", "45411"),
    ("Ciamis", "102", "9", "Jawa Barat", "46211"),
    ("Banjar", "34", "9", "Jawa Barat", "46311"),
    # DI Yogyakarta
    ("Yogyakarta", "501", "5", "DI Yogyakarta", "55111"),
    ("Sleman", "419", "5", "DI Yogyakarta", "55511"),
    ("Bantul", "39", "5", "DI Yogyakarta", "55711"),
    ("Kulon Progo", "210", "5", "DI Yogyakarta", "55611"),
    ("Gunung Kidul", "135", "5", "DI Yogyakarta", "55811"),
    # Jawa Tengah
    ("Semarang", "399", "10", "Jawa Tengah", "50111"),
    ("Kab. Semarang", "398", "10", "Jawa Tengah", "50511"),
    ("Surakarta", "445", "10", "Jawa Tengah", "57111"),
    ("Magelang", "249", "10", "Jawa Tengah", "56111"),
    ("Salatiga", "386", "10", "Jawa Tengah", "50711"),
    ("Pekalongan", "349", "10", "Jawa Tengah", "51111"),
    ("Tegal", "473", "10", "Jawa Tengah", "52111"),
    ("Banyumas", "41", "10", "Jawa Tengah", "53111"),
    ("Cilacap", "105", "10", "Jawa Tengah", "53211"),
    ("Kudus", "209", "10", "Jawa Tengah", "59311"),
    ("Jepara", "163", "10", "Jawa Tengah", "59411"),
    ("Pati", "344", "10", "Jawa Tengah", "59111"),
    ("Klaten", "196", "10", "Jawa Tengah", "57411"),
    ("Sukoharjo", "433", "10", "Jawa Tengah", "57511"),
    ("Karanganyar", "169", "10", "Jawa Tengah", "57711"),
    ("Boyolali", "91", "10", "Jawa Tengah", "57311"),
    ("Sragen", "427", "10", "Jawa Tengah", "57211"),
    ("Kebumen", "177", "10", "Jawa Tengah", "54311"),
    ("Kendal", "181", "10", "Jawa Tengah", "51311"),
    ("Demak", "113", "10", "Jawa Tengah", "59511"),
    ("Brebes", "92", "10", "Jawa Tengah", "52211"),
    ("Pemalang", "352", "10", "Jawa Tengah", "52311"),
    ("Purbalingga", "375", "10", "Jawa Tengah", "53311"),
    ("Wonosobo", "498", "10", "Jawa Tengah", "56311"),
    # Jawa Timur
    ("Surabaya", "444", "11", "Jawa Timur", "60111"),
    ("Malang", "256", "11", "Jawa Timur", "65111"),
    ("Kab. Malang", "255", "11", "Jawa Timur", "65163"),
    ("Batu", "51", "11", "Jawa Timur", "65311"),
    ("Sidoarjo", "409", "11", "Jawa Timur", "61211"),
    ("Gresik", "133", "11", "Jawa Timur", "61111"),
    ("Mojokerto", "290", "11", "Jawa Timur", "61311"),
    ("Pasuruan", "343", "11", "Jawa Timur", "67111"),
    ("Probolinggo", "370", "11", "Jawa Timur", "67211"),
    ("Kediri", "179", "11", "Jawa Timur", "64111"),
    ("Blitar", "75", "11", "Jawa Timur", "66111"),
    ("Madiun", "248", "11", "Jawa Timur", "63111"),
    ("Jember", "160", "11", "Jawa Timur", "68111"),
    ("Banyuwangi", "42", "11", "Jawa Timur", "68411"),
    ("Bojonegoro", "80", "11", "Jawa Timur", "62111"),
    ("Tuban", "489", "11", "Jawa Timur", "62311"),
    ("Lamongan", "222", "11", "Jawa Timur", "62211"),
    ("Jombang", "164", "11", "Jawa Timur", "61411"),
    ("Tulungagung", "492", "11", "Jawa Timur", "66211"),
    ("Ponorogo", "363", "11", "Jawa Timur", "63411"),
    ("Lumajang", "243", "11", "Jawa Timur", "67311"),
    ("Bangkalan", "27", "11", "Jawa Timur", "69111"),
    # Bali
    ("Denpasar", "114", "1", "Bali", "80111"),
    ("Badung", "17", "1", "Bali", "80351"),
    ("Gianyar", "128", "1", "Bali", "80511"),
    ("Tabanan", "447", "1", "Bali", "82111"),
    ("Buleleng", "94", "1", "Bali", "81111"),
    ("Karangasem", "170", "1", "Bali", "80811"),
    ("Klungkung", "197", "1", "Bali", "80711"),
    ("Bangli", "32", "1", "Bali", "80611"),
    ("Jembrana", "161", "1", "Bali", "82211"),
    # Nusa Tenggara Barat
    ("Mataram", "276", "22", "Nusa Tenggara Barat", "83111"),
    ("Lombok Barat", "238", "22", "Nusa Tenggara Barat", "83311"),
    ("Lombok Tengah", "239", "22", "Nusa Tenggara Barat", "83511"),
    ("Lombok Timur", "240", "22", "Nusa Tenggara Barat", "83611"),
    ("Bima", "69", "22", "Nusa Tenggara Barat", "84111"),
    ("Sumbawa", "438", "22", "Nusa Tenggara Barat", "84311"),
    # Nusa Tenggara Timur
    ("Kupang", "213", "23", "Nusa Tenggara Timur", "85111"),
    ("Manggarai Barat", "264", "23", "Nusa Tenggara Timur", "86754"),
    ("Ende", "122", "23", "Nusa Tenggara Timur", "86311"),
    ("Sikka", "412", "23", "Nusa Tenggara Timur", "86111"),
    # Aceh
    ("Banda Aceh", "20", "21", "Aceh", "23111"),
    ("Lhokseumawe", "235", "21", "Aceh", "24311"),
    ("Langsa", "230", "21", "Aceh", "24411"),
    ("Sabang", "384", "21", "Aceh", "23511"),
    # Sumatera Utara
    ("Medan", "278", "34", "Sumatera Utara", "20111"),
    ("Binjai", "70", "34", "Sumatera Utara", "20711"),
    ("Deli Serdang", "112", "34", "Sumatera Utara", "20511"),
    ("Pematang Siantar", "353", "34", "Sumatera Utara", "21111"),
    ("Tebing Tinggi", "470", "34", "Sumatera Utara", "20611"),
    ("Padang Sidempuan", "319", "34", "Sumatera Utara", "22711"),
    ("Sibolga", "407", "34", "Sumatera Utara", "22511"),
    # Sumatera Barat
    ("Padang", "318", "32", "Sumatera Barat", "25111"),
    ("Bukittinggi", "93", "32", "Sumatera Barat", "26111"),
    ("Payakumbuh", "345", "32", "Sumatera Barat", "26211"),
    ("Padang Panjang", "316", "32", "Sumatera Barat", "27111"),
    ("Solok", "421", "32", "Sumatera Barat", "27311"),
    ("Pariaman", "339", "32", "Sumatera Barat", "25511"),
    # Riau
    ("Pekanbaru", "350", "26", "Riau", "28111"),
    ("Dumai", "120", "26", "Riau", "28811"),
    ("Kampar", "166", "26", "Riau", "28411"),
    ("Siak", "406", "26", "Riau", "28671"),
    # Kepulauan Riau
    ("Batam", "48", "17", "Kepulauan Riau", "29411"),
    ("Tanjung Pinang", "462", "17", "Kepulauan Riau", "29111"),
    ("Bintan", "71", "17", "Kepulauan Riau", "29151"),
    # Jambi
    ("Jambi", "156", "8", "Jambi", "36111"),
    ("Sungai Penuh", "442", "8", "Jambi", "37111"),
    # Sumatera Selatan
    ("Palembang", "327", "33", "Sumatera Selatan", "30111"),
    ("Lubuk Linggau", "242", "33", "Sumatera Selatan", "31611"),
    ("Prabumulih", "367", "33", "Sumatera Selatan", "31111"),
    ("Pagar Alam", "321", "33", "Sumatera Selatan", "31511"),
    # Bangka Belitung
    ("Pangkal Pinang", "334", "2", "Bangka Belitung", "33111"),
    ("Belitung", "56", "2", "Bangka Belitung", "33411"),
    # Bengkulu
    ("Bengkulu", "62", "4", "Bengkulu", "38111"),
    # Lampung
    ("Bandar Lampung", "21", "18", "Lampung", "35111"),
    ("Metro", "283", "18", "Lampung", "34111"),
    ("Lampung Selatan", "224", "18", "Lampung", "35511"),
    # Kalimantan Barat
    ("Pontianak", "365", "12", "Kalimantan Barat", "78111"),
    ("Singkawang", "415", "12", "Kalimantan Barat", "79111"),
    ("Kubu Raya", "208", "12", "Kalimantan Barat", "78391"),
    # Kalimantan Tengah
    ("Palangka Raya", "326", "14", "Kalimantan Tengah", "73111"),
    ("Kotawaringin Timur", "206", "14", "Kalimantan Tengah", "74311"),
    # Kalimantan Selatan
    ("Banjarmasin", "36", "13", "Kalimantan Selatan", "70111"),
    ("Banjarbaru", "35", "13", "Kalimantan Selatan", "70711"),
    # Kalimantan Timur
    ("Balikpapan", "19", "15", "Kalimantan Timur", "76111"),
    ("Samarinda", "387", "15", "Kalimantan Timur", "75111"),
    ("Bontang", "89", "15", "Kalimantan Timur", "75311"),
    ("Kutai Kartanegara", "215", "15", "Kalimantan Timur", "75511"),
    # Kalimantan Utara
    ("Tarakan", "467", "16", "Kalimantan Utara", "77111"),
    # Sulawesi Utara
    ("Manado", "267", "31", "Sulawesi Utara", "95111"),
    ("Bitung", "73", "31", "Sulawesi Utara", "95511"),
    ("Tomohon", "486", "31", "Sulawesi Utara", "95411"),
    # Gorontalo
    ("Gorontalo", "130", "7", "Gorontalo", "96111"),
    # Sulawesi Tengah
    ("Palu", "329", "29", "Sulawesi Tengah", "94111"),
    # Sulawesi Barat
    ("Mamuju", "262", "27", "Sulawesi Barat", "91511"),
    # Sulawesi Selatan
    ("Makassar", "254", "28", "Sulawesi Selatan", "90111"),
    ("Parepare", "336", "28", "Sulawesi Selatan", "91111"),
    ("Palopo", "328", "28", "Sulawesi Selatan", "91911"),
    ("Gowa", "131", "28", "Sulawesi Selatan", "92111"),
    ("Maros", "275", "28", "Sulawesi Selatan", "90511"),
    # Sulawesi Tenggara
    ("Kendari", "182", "30", "Sulawesi Tenggara", "93111"),
    ("Bau-Bau", "53", "30", "Sulawesi Tenggara", "93711"),
    # Maluku & Maluku Utara
    ("Ambon", "14", "19", "Maluku", "97111"),
    ("Tual", "488", "19", "Maluku", "97611"),
    ("Ternate", "477", "20", "Maluku Utara", "97711"),
    ("Tidore Kepulauan", "478", "20", "Maluku Utara", "97811"),
    # Papua & Papua Barat
    ("Jayapura", "158", "24", "Papua", "99111"),
    ("Merauke", "281", "24", "Papua", "99611"),
    ("Mimika", "284", "24", "Papua", "99911"),
    ("Nabire", "303", "24", "Papua", "98811"),
    ("Biak Numfor", "67", "24", "Papua", "98111"),
    ("Sorong", "425", "25", "Papua Barat", "98411"),
    ("Manokwari", "272", "25", "Papua Barat", "98311"),
]

RAJAONGKIR_CITY_MAP = {
    name.lower(): (city_id, prov_id, prov_name)
    for name, city_id, prov_id, prov_name, _ in INDONESIAN_CITIES
}

CITY_POSTAL_MAP = {
    name.lower(): postal
    for name, _, _, _, postal in INDONESIAN_CITIES
}

CITY_DISPLAY_MAP = {
    name.lower(): name
    for name, _, _, _, _ in INDONESIAN_CITIES
}

CITY_ALIASES = {
    "solo": "surakarta",
    "kota solo": "surakarta",
    "jogja": "yogyakarta",
    "jogjakarta": "yogyakarta",
    "jakarta": "jakarta pusat",
    "dki jakarta": "jakarta pusat",
    "jaksel": "jakarta selatan",
    "jakpus": "jakarta pusat",
    "jakbar": "jakarta barat",
    "jaktim": "jakarta timur",
    "jakut": "jakarta utara",
    "tangsel": "tangerang selatan",
    "purwokerto": "banyumas",
    "labuan bajo": "manggarai barat",
    "kuta": "badung",
    "ubud": "gianyar",
    "palangkaraya": "palangka raya",
    "tanjungpinang": "tanjung pinang",
    "pangkalpinang": "pangkal pinang",
    "lubuklinggau": "lubuk linggau",
    "pematangsiantar": "pematang siantar",
    "padangsidempuan": "padang sidempuan",
    "baubau": "bau-bau",
    "gunungkidul": "gunung kidul",
    "kulonprogo": "kulon progo",
    "bandarlampung": "bandar lampung",
    "sungaipenuh": "sungai penuh",
    "banjar baru": "banjarbaru",
    "ujung pandang": "makassar",
}

CITY_CHOICES = [("", "Pilih kota / kabupaten")] + [
    (name, f"{name} ({prov_name})")
    for name, _, _, prov_name, _ in INDONESIAN_CITIES
]


def get_city_groups():
    """Daftar kota dikelompokkan per provinsi untuk <optgroup> di dropdown."""
    groups = {}
    for name, city_id, _, prov_name, postal in INDONESIAN_CITIES:
        groups.setdefault(prov_name, []).append({
            "name": name,
            "city_id": city_id,
            "province": prov_name,
            "postal_code": postal,
        })
    return list(groups.items())


_UPPER_TOKENS = {"dki", "di", "ntb", "ntt", "nad", "diy"}


def format_region_name(raw: str) -> str:
    """Ubah nama wilayah dari API (sering HURUF KAPITAL) jadi kapitalisasi rapi."""
    if not raw:
        return ""
    cleaned = re.sub(r"\s+", " ", raw.strip())
    words = []
    for word in cleaned.split(" "):
        low = word.lower()
        if low in _UPPER_TOKENS:
            words.append(low.upper())
        elif low == "kab.":
            words.append("Kab.")
        elif low == "kep.":
            words.append("Kep.")
        else:
            words.append(low.capitalize())
    return " ".join(words)


def normalize_city_key(city_name: str) -> str:
    """Normalisasi nama kota agar 'KOTA DEPOK', 'Kota Administrasi Jakarta Selatan', dll. cocok."""
    if not city_name:
        return ""
    key = re.sub(r"\s+", " ", city_name.strip().lower())
    if key in CITY_ALIASES:
        return CITY_ALIASES[key]
    if key in RAJAONGKIR_CITY_MAP:
        return key

    # Bedakan "kabupaten X" vs "kota X"
    if key.startswith("kabupaten "):
        rest = key[len("kabupaten "):].strip()
        if f"kab. {rest}" in RAJAONGKIR_CITY_MAP:
            return f"kab. {rest}"
        if rest in RAJAONGKIR_CITY_MAP:
            return rest
    if key.startswith("kab. "):
        rest = key[len("kab. "):].strip()
        if key in RAJAONGKIR_CITY_MAP:
            return key
        if rest in RAJAONGKIR_CITY_MAP:
            return rest

    for prefix in ("kota administrasi ", "kota "):
        if key.startswith(prefix):
            rest = key[len(prefix):].strip()
            if rest in CITY_ALIASES:
                return CITY_ALIASES[rest]
            if rest in RAJAONGKIR_CITY_MAP:
                return rest
    return key


def resolve_rajaongkir_city(city_name: str):
    """Kembalikan (rajaongkir_city_id, rajaongkir_province_id, province_name) untuk nama kota."""
    if not city_name:
        return ("", "", "")
    key = normalize_city_key(city_name)
    if key in RAJAONGKIR_CITY_MAP:
        return RAJAONGKIR_CITY_MAP[key]

    # Cocokkan kata utuh dari nama kota terpanjang agar "Tangerang Selatan" tidak jatuh ke "Tangerang"
    for map_key in sorted(RAJAONGKIR_CITY_MAP, key=len, reverse=True):
        if re.search(rf"(?:^|\b){re.escape(map_key)}(?:\b|$)", key):
            return RAJAONGKIR_CITY_MAP[map_key]
    return ("", "", "")


def canonical_city_name(city_name: str) -> str:
    """Kembalikan nama tampilan standar jika ada di katalog, atau format rapi jika kota baru."""
    if not city_name:
        return ""
    key = normalize_city_key(city_name)
    if key in CITY_DISPLAY_MAP:
        return CITY_DISPLAY_MAP[key]
    cleaned = re.sub(r"^kota\s+administrasi\s+", "", city_name.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"^kota\s+", "", cleaned, flags=re.IGNORECASE)
    return format_region_name(cleaned)


def get_default_postal_code(city_name: str) -> str:
    if not city_name:
        return ""
    key = normalize_city_key(city_name)
    return CITY_POSTAL_MAP.get(key, "")


def search_local_cities(query: str, limit: int = 15):
    """Pencarian lokal berdasarkan nama kota, alias, provinsi, atau awalan kode pos."""
    q = (query or "").strip().lower()
    if not q:
        return []
    alias_target = CITY_ALIASES.get(q)
    matches = []
    seen = set()

    def _add(entry, score):
        name, city_id, _, prov_name, postal = entry
        if name.lower() in seen:
            return
        seen.add(name.lower())
        matches.append((score, {
            "destination_id": "",
            "rajaongkir_city_id": city_id,
            "label": f"{name}, {prov_name} ({postal})",
            "subdistrict": "",
            "district": "",
            "city": name,
            "province": prov_name,
            "postal_code": postal,
            "source": "local",
        }))

    for entry in INDONESIAN_CITIES:
        name, _, _, prov_name, postal = entry
        n_low = name.lower()
        p_low = prov_name.lower()
        if alias_target and n_low == alias_target:
            _add(entry, 0)
        elif n_low == q:
            _add(entry, 0)
        elif n_low.startswith(q):
            _add(entry, 1)
        elif q in n_low:
            _add(entry, 2)
        elif q.isdigit() and postal.startswith(q):
            _add(entry, 2)
        elif q in p_low:
            _add(entry, 3)

    # Cek alias parsial (mis. "jog" -> Yogyakarta, "purwo" -> Banyumas)
    for alias, target in CITY_ALIASES.items():
        if q in alias and target in CITY_DISPLAY_MAP:
            for entry in INDONESIAN_CITIES:
                if entry[0].lower() == target:
                    _add(entry, 1)
                    break

    matches.sort(key=lambda item: (item[0], item[1]["city"]))
    return [item[1] for item in matches[:limit]]
