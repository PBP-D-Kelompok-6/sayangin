from datetime import datetime, time, timedelta

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from impact import sources
from impact.forms import ChallengeForm
from impact.models import Challenge
from main.decorators import personal_required

# Create your views here.

# Lencananya (Achievements): Jika terpenuhi maka dapat lencananya
# hanya dibaca oleh get_badges()
BADGES = [
    ("Sayangin Starter", "Catat 1 barang di lemari", "lemari", 1),
    ("Second Life", "Jual 1 barang preloved", "terjual", 1),
    ("Pembeli Bijak", "Beli 3 barang preloved", "dibeli", 3),
    ("First Giving", "1 donasi diterima lembaga", "donasi", 1),
    ("Kind Closet", "3 donasi diterima lembaga", "donasi", 3),
    ("Lemari Rapi", "Catat 10 barang di lemari", "lemari", 10),
]

def start_of(day):
    return timezone.make_aware(datetime.combine(day, time.min))

# Untuk tiap jenis di Sources: hitung aksi user
# Dipakai untuk build_dashboard() html
# misal: "lemari":5, "donasi":3, etc
def get_counts(user, since=None):
    return {key: sources.count_for_user(key, user, since) for key in sources.SOURCES}


# Menerima hasil get_counts(), return status tiap lencana/badges
# Dipanggil build_dashboard() : dashboard.html {% for badges in BADGES %}
def get_badges(counts):
    return [
        {"name": name, "rule": rule, "earned": counts[key] >= minimum,
         "percent": min(round(counts[key] / minimum * 100), 100)}
        for name, rule, key, minimum in BADGES
    ]

# Dipanggil get_next_step() /dashboard dan show_impact_challenges() /daftar
def challenge_progress(challenge, user):
    done = sources.count_for_user(challenge.kind, user, since=start_of(challenge.start_date),
                                  until=start_of(challenge.end_date + timedelta(days=1)))
    done = min(done, challenge.target)
    return {"challenge": challenge, "done": done, "percent": round(done / challenge.target * 100),
            "remaining": challenge.target - done}

# Challenges yang sisanya paling dikit (Langkah berikutnya)
# Dipanggil show_impact_dashboard() : di template {% if next_step %}
def get_next_step(user):
    running = Challenge.objects.filter(owner=user, end_date__gte=timezone.localdate())
    unfinished = [row for row in (challenge_progress(c, user) for c in running) if row["remaining"] > 0]
    return min(unfinished, key=lambda row: row["remaining"]) if unfinished else None

# tergantung periode: semua/bulan ini
# dipanggil sohw_impact_dashboard() dan show_impact_json
# key nya muncul di summary.html
def build_dashboard(request):
    period = "semua" if request.GET.get("periode") == "semua" else "bulan"
    since = None if period == "semua" else start_of(timezone.localdate().replace(day=1)) # kalau "bulan ini" start dari tanggal 1 bulan tsb
    counts = get_counts(request.user, since) # hitung sesuai since/periodenya (untuk angka & poin)
    badges = get_badges(get_counts(request.user)) 
    return {
        "period": period,
        "points": sum(counts[key] * sources.POINTS[key] for key in counts), # jumlah aksi * poin aksi
        "stats": [{"key": key, "label": sources.LABELS[key], "value": counts[key], "points": sources.POINTS[key]}
                  for key in counts], # kartu angka: label, angka, dan "+N poin/aksi"
        "badges": badges, # lencana
        "earned_count": sum(1 for badge in badges if badge["earned"]), # TOTAL POIN DAMPAK, hitung lencana yang sudah diraih: jumlahkan angka 1 untuk setiap yang earned
    }

# menampilkan html page: dashboard.html && summary.html
# Manggil build_dashboard() /di atasnya
@personal_required
def show_impact_dashboard(request):
    context = build_dashboard(request)  
    if request.headers.get("HX-Request"): 
        return render(request, "impact/partials/summary.html", context)
    context["next_step"] = get_next_step(request.user)
    return render(request, "impact/dashboard.html", context)


@personal_required
def show_impact_json(request):
    return JsonResponse(build_dashboard(request)) # sebagai Json


# menampilkan html page: challenges.html & challenges_list.html
@personal_required
def show_impact_challenges(request):
    kind = request.GET.get("jenis", "")
    status = request.GET.get("status", "")
    rows = Challenge.objects.filter(owner=request.user)
    if kind:
        rows = rows.filter(kind=kind)
    today = timezone.localdate()
    if status == "berjalan":
        rows = rows.filter(end_date__gte=today)
    elif status == "berakhir":
        rows = rows.filter(end_date__lt=today)
    context = {
        "rows": [challenge_progress(challenge, request.user) for challenge in rows],
        "kind": kind,
        "status": status,
        "kinds": Challenge.KIND_CHOICES,
    }
    if request.headers.get("HX-Request"):
        return render(request, "impact/partials/challenge_list.html", context)
    return render(request, "impact/challenges.html", context)

# menampilkan html page: challenges_form.html
@personal_required
def create_impact_challenge(request):
    today = timezone.localdate()
    form = ChallengeForm(request.POST or None, initial={"start_date": today, "end_date": today + timedelta(days=7)})
    if form.is_valid():
        challenge = form.save(commit=False)
        challenge.owner = request.user
        challenge.save()
        return redirect("impact:show_impact_challenges")
    return render(request, "impact/challenge_form.html", {"form": form})

# menampilkan html page: challenges_form.html
@personal_required
def edit_impact_challenge(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk, owner=request.user)
    form = ChallengeForm(request.POST or None, instance=challenge)
    if form.is_valid():
        form.save()
        return redirect("impact:show_impact_challenges")
    return render(request, "impact/challenge_form.html", {"form": form, "is_edit": True})


@personal_required
@require_POST
def delete_impact_challenge(request, pk):
    get_object_or_404(Challenge, pk=pk, owner=request.user).delete()
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("impact:show_impact_challenges")