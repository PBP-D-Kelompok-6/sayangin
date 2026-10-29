from datetime import datetime, time, timedelta

from django.contrib.auth.models import User # untuk mengambil username di papan peringkat
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST # batasi method request (GET saja / POST saja)

from impact import sources
from impact.forms import ChallengeForm
from impact.models import Challenge
from main.decorators import personal_required
from main.models import UserProfile # role akun (PERSONAL / LEMBAGA) milik modul autentikasi tim

# Create your views here.

# Lencananya (Achievements): Jika terpenuhi maka dapat lencananya
# Hanya dibaca oleh get_badges()
# Isi tiap baris: (nama, syarat, jenis aksi di SOURCES, jumlah minimal, gambar di static/)
BADGES = [
    ("Sayangin Starter", "Catat 1 barang di lemari", "lemari", 1, "img/lencana-lemari.jpg"),
    ("Second Life", "Jual 1 barang preloved", "terjual", 1, "img/lencana-penyelamat.jpg"),
    ("Pembeli Bijak", "Beli 3 barang preloved", "dibeli", 3, "img/lencana-tunda.jpg"),
    ("First Giving", "1 donasi diterima lembaga", "donasi", 1, "img/lencana-donatur.jpg"),
    ("Kind Closet", "3 donasi diterima lembaga", "donasi", 3, "img/lencana-donatur.jpg"),
    ("Lemari Rapi", "Catat 10 barang di lemari", "lemari", 10, "img/lencana-lemari.jpg"),
]

# Ubah tanggal (date) jadi datetime jam 00.00 sesuai zona waktu,
# supaya bisa dibandingkan dengan kolom tanggal+jam dari source modul lain
def start_of(day):
    return timezone.make_aware(datetime.combine(day, time.min))

# untuk tiap jenis di Sources: hitung aksi user
# dipakai untuk build_dashboard() html
# misal: "lemari":5, "donasi":3, etc
def get_counts(user, since=None):
    return {key: sources.count_for_user(key, user, since) for key in sources.SOURCES}


# menerima hasil get_counts(), return status tiap lencana/badges
# dipanggil build_dashboard() : dashboard.html {% for badges in BADGES %}
# lencana tidak disimpan di database, selalu dihitung ulang dari jumlah aksi
def get_badges(counts):
    return [
        {"name": name, "rule": rule, "image": image, "earned": counts[key] >= minimum, # earned: sudah mencapai minimal
         "percent": min(round(counts[key] / minimum * 100), 100)} # progres lencana, paling besar 100%
        for name, rule, key, minimum, image in BADGES
    ]

# dipanggil get_dashboard_challenges() /dashboard dan show_impact_challenges() /daftar
def challenge_progress(challenge, user):
    # hitung aksi di antara tanggal mulai dan selesai; +1 hari supaya tanggal selesai ikut terhitung
    done = sources.count_for_user(challenge.kind, user, since=start_of(challenge.start_date),
                                  until=start_of(challenge.end_date + timedelta(days=1)))
    done = min(done, challenge.target) # tidak boleh melebihi target (mis. 5/3 -> 3/3)
    return {"challenge": challenge, "done": done, "percent": round(done / challenge.target * 100),
            "remaining": challenge.target - done} # remaining = sisa yang belum dikerjakan

# Tantangan untuk dashboard: "Langkah berikutnya" + bagian "Tantangan kamu"
# dipanggil show_impact_dashboard() : di template {% if next_step %} dan {% for row in challenges %}
def get_dashboard_challenges(user):
    running = Challenge.objects.filter(owner=user, end_date__gte=timezone.localdate()) # hanya yang masih berjalan
    unfinished = [row for row in (challenge_progress(c, user) for c in running) if row["remaining"] > 0] # buang yang sudah selesai
    # langkah berikutnya = sisa paling sedikit; None -> tampil ajakan buat tantangan
    next_step = min(unfinished, key=lambda row: row["remaining"]) if unfinished else None
    # tantangan kamu = deadline paling dekat dulu; kalau deadline-nya sama, yang sisanya paling sedikit dulu
    upcoming = sorted(unfinished, key=lambda row: (row["challenge"].end_date, row["remaining"]))
    return {
        "next_step": next_step,
        "challenges": upcoming[:4], # maksimal 4 kartu, sesuai desain Figma
        "challenge_total": Challenge.objects.filter(owner=user).count(), # angka di link "Lihat semua (N)"
    }

# Papan peringkat: total poin semua pengguna personal, urut dari yang terbesar
# dipanggil build_dashboard(); since = periode (None -> sepanjang waktu)
def get_leaderboard(since=None):
    scores = {} # {id_user: total poin}
    for key, point in sources.POINTS.items():
        for user_id, total in sources.count_per_user(key, since).items():
            scores[user_id] = scores.get(user_id, 0) + total * point # jumlah aksi * poin aksi, ditambahkan per jenis
    users = User.objects.filter(id__in=scores, profile__role="PERSONAL") 
    ranking = sorted(users, key=lambda u: (-scores[u.id], u.username)) # poin terbesar dulu: kalau seri, urut username
    return [{"rank": i, "username": u.username, "user_id": u.id, "points": scores[u.id]}
            for i, u in enumerate(ranking, start=1)]

# Baca pilihan periode dari URL (?periode=semua / ?periode=bulan) -> (period, since)
# dipakai build_dashboard() dan show_impact_leaderboard() supaya aturannya sama
def get_period(request):
    period = "semua" if request.GET.get("periode") == "semua" else "bulan" # selain "semua", default-nya bulan ini
    since = None if period == "semua" else start_of(timezone.localdate().replace(day=1)) # kalau "bulan ini" start dari tanggal 1 bulan tsb
    return period, since

# tergantung periode: semua/bulan ini
# dipanggil show_impact_dashboard() dan show_impact_json
# key nya muncul di summary.html
def build_dashboard(request):
    period, since = get_period(request)
    counts = get_counts(request.user, since) # hitung sesuai since/periodenya (untuk angka & poin)
    badges = get_badges(get_counts(request.user)) # lencana selalu dihitung sepanjang waktu (tanpa since)
    leaderboard = get_leaderboard(since) # peringkat ikut periode, sama seperti angka & poin
    return {
        "period": period,
        "points": sum(counts[key] * sources.POINTS[key] for key in counts), # jumlah aksi * poin aksi
        "stats": [{"key": key, "label": sources.LABELS[key], "value": counts[key], "points": sources.POINTS[key]}
                  for key in counts], # kartu angka: label, angka, dan "+N poin/aksi"
        "badges": badges, # lencana
        "earned_count": sum(1 for badge in badges if badge["earned"]), # JUMLAH LENCANA YANG SUDAH DIRAIH, hitung lencana yang sudah diraih: jumlahkan angka 1 untuk setiap yang earned
        "leaderboard": leaderboard[:5], # dashboard cukup 5 teratas
        # posisi user yang login (bisa di luar 5 teratas); None kalau belum punya poin di periode ini
        "my_rank": next((row for row in leaderboard if row["user_id"] == request.user.id), None),
    }

# menampilkan html page: dashboard.html && summary.html
# manggil build_dashboard() /di atasnya
def show_impact_dashboard(request):
    # semua link "Dampak" di web mengarah ke sini; tamu & lembaga dialihkan ke papan peringkat publik
    # (bukan ke halaman login / error 403), karena dashboard hanya untuk akun personal
    if not request.user.is_authenticated:
        return redirect("impact:show_impact_leaderboard")
    profile, _ = UserProfile.objects.get_or_create(user=request.user) # sama seperti personal_required milik tim
    if profile.role != "PERSONAL":
        return redirect("impact:show_impact_leaderboard")
    context = build_dashboard(request)
    # tombol periode memakai HTMX -> cukup kirim potongan summary.html, bukan satu halaman
    if request.headers.get("HX-Request"):
        return render(request, "impact/partials/summary.html", context)
    context.update(get_dashboard_challenges(request.user)) # next_step, challenges, challenge_total; hanya perlu saat halaman dibuka penuh
    return render(request, "impact/dashboard.html", context)


# data dashboard yang sama dengan halaman HTML, tapi dalam bentuk JSON (/dampak/json/)
@personal_required
def show_impact_json(request):
    return JsonResponse(build_dashboard(request)) # sebagai Json


# Halaman papan peringkat publik (/dampak/peringkat/)
# SENGAJA tanpa @personal_required: tamu & lembaga boleh melihat, tapi isinya dibedakan di template
@require_GET
def show_impact_leaderboard(request):
    period, since = get_period(request)
    leaderboard = get_leaderboard(since)
    context = {
        "period": period,
        "leaderboard": leaderboard[:10], # halaman publik menampilkan 10 teratas
        # posisi user yang login; tamu (belum login) selalu None
        "my_rank": next((row for row in leaderboard if row["user_id"] == request.user.id), None)
                   if request.user.is_authenticated else None,
    }
    return render(request, "impact/leaderboard.html", context)


# menampilkan html page: challenges.html & challenges_list.html
@personal_required
def show_impact_challenges(request):
    # nilai filter dari URL, mis. ?jenis=donasi&status=berjalan ("" = semua)
    kind = request.GET.get("jenis", "")
    status = request.GET.get("status", "")
    rows = Challenge.objects.filter(owner=request.user) # hanya tantangan milik user yang login
    if kind:
        rows = rows.filter(kind=kind)
    today = timezone.localdate()
    if status == "berjalan":
        rows = rows.filter(end_date__gte=today) # tanggal selesai hari ini atau nanti
    elif status == "berakhir":
        rows = rows.filter(end_date__lt=today) # tanggal selesai sudah lewat
    context = {
        "rows": [challenge_progress(challenge, request.user) for challenge in rows], # tiap tantangan + progresnya
        "kind": kind, # dipakai template untuk menandai pilihan filter yang aktif
        "status": status,
        "kinds": Challenge.KIND_CHOICES, # isi dropdown "Semua jenis"
    }
    # filter berubah lewat HTMX -> cukup kirim potongan daftarnya
    if request.headers.get("HX-Request"):
        return render(request, "impact/partials/challenge_list.html", context)
    return render(request, "impact/challenges.html", context)

# menampilkan html page: challenges_form.html
@personal_required
def create_impact_challenge(request):
    today = timezone.localdate()
    # GET -> form kosong (default 7 hari dari hari ini), POST -> form berisi data kiriman
    form = ChallengeForm(request.POST or None, initial={"start_date": today, "end_date": today + timedelta(days=7)})
    if form.is_valid():
        challenge = form.save(commit=False) # belum disimpan dulu...
        challenge.owner = request.user # ...isi pemiliknya otomatis, bukan dari input user
        challenge.save()
        return redirect("impact:show_impact_challenges")
    return render(request, "impact/challenge_form.html", {"form": form}) # form tidak valid -> tampil lagi dengan error

# menampilkan html page: challenges_form.html
@personal_required
def edit_impact_challenge(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk, owner=request.user) # milik orang lain -> 404
    form = ChallengeForm(request.POST or None, instance=challenge) # instance: form terisi data lama
    if form.is_valid():
        form.save()
        return redirect("impact:show_impact_challenges")
    return render(request, "impact/challenge_form.html", {"form": form, "is_edit": True}) # is_edit: judul jadi "Ubah"


# hapus tantangan, hanya lewat POST (link biasa/GET -> 405)
@personal_required
@require_POST
def delete_impact_challenge(request, pk):
    get_object_or_404(Challenge, pk=pk, owner=request.user).delete() # milik orang lain -> 404
    # lewat HTMX: balas kosong, kartunya langsung hilang tanpa reload
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("impact:show_impact_challenges")
