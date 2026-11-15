# API Modul E (Dampak) untuk aplikasi Flutter, dibuat dengan Django REST Framework
# Disambungkan di impact/urls.py dengan awalan "api/" -> /dampak/api/...
# Semua angka memakai fungsi yang sama dengan halaman web (views.py), jadi aplikasi & situs selalu sama
from django.templatetags.static import static
from rest_framework import permissions, serializers, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from impact import sources
from impact.models import Challenge
from impact.views import (build_dashboard, challenge_progress, filter_challenges, get_dashboard_challenges,
                          get_leaderboard, get_period, mask_username)
from main.models import UserProfile


# Login dari Flutter memakai session cookie (seperti pbp_django_auth di tutorial)
# CSRF sengaja tidak dicek, karena aplikasi HP tidak punya form HTML yang membawa token CSRF
class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


# Hanya akun personal yang boleh (sama seperti @personal_required di views.py)
class IsPersonal(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return profile.role == "PERSONAL"


# Tantangan + progresnya; dipakai daftar, detail, tambah, dan ubah
class ChallengeSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True) # mis. "Donasi diterima lembaga"
    is_running = serializers.BooleanField(read_only=True)
    done = serializers.SerializerMethodField()
    percent = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()

    class Meta:
        model = Challenge
        fields = ["id", "title", "kind", "kind_label", "target", "start_date", "end_date",
                  "is_running", "done", "percent", "remaining"]

    # progres dihitung sekali per tantangan, lalu dipakai tiga field di atas
    def _progress(self, challenge):
        cache = self.context.setdefault("progress", {})
        if challenge.pk not in cache:
            cache[challenge.pk] = challenge_progress(challenge, self.context["request"].user)
        return cache[challenge.pk]

    def get_done(self, challenge):
        return self._progress(challenge)["done"]

    def get_percent(self, challenge):
        return self._progress(challenge)["percent"]

    def get_remaining(self, challenge):
        return self._progress(challenge)["remaining"]

    # validasi sama dengan ChallengeForm.clean()
    def validate_target(self, value):
        if value < 1:
            raise serializers.ValidationError("Target minimal 1.")
        return value

    def validate(self, data):
        # saat PATCH, field yang tidak dikirim diambil dari data lama
        start = data.get("start_date", getattr(self.instance, "start_date", None))
        end = data.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "Tanggal selesai tidak boleh sebelum tanggal mulai."})
        return data


# CRUD tantangan: /dampak/api/tantangan/ dan /dampak/api/tantangan/<id>/
# filter sama dengan halaman web: ?jenis=donasi&status=berjalan
class ChallengeViewSet(viewsets.ModelViewSet):
    serializer_class = ChallengeSerializer
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsPersonal]

    def get_queryset(self):
        rows = Challenge.objects.filter(owner=self.request.user) # milik orang lain tidak ikut -> 404
        if self.action == "list":
            rows = filter_challenges(rows, self.request.GET.get("jenis", ""), self.request.GET.get("status", ""))
        return rows

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user) # pemilik diisi otomatis, bukan dari input


# Dashboard: /dampak/api/dashboard/?periode=bulan|semua
@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsPersonal])
def dashboard_api(request):
    data = build_dashboard(request)
    # gambar lencana diubah jadi URL lengkap supaya bisa dipakai Image.network di Flutter
    data["badges"] = [{**badge, "image": request.build_absolute_uri(static(badge["image"]))}
                      for badge in data["badges"]]
    extra = get_dashboard_challenges(request.user)
    context = {"request": request}
    next_step = extra["next_step"]
    data["next_step"] = ChallengeSerializer(next_step["challenge"], context=context).data if next_step else None
    data["challenges"] = ChallengeSerializer([row["challenge"] for row in extra["challenges"]],
                                             many=True, context=context).data
    data["challenge_total"] = extra["challenge_total"]
    return Response(data)


# Papan peringkat: /dampak/api/peringkat/?periode=bulan|semua
# tamu boleh membuka, tapi namanya disamarkan (sama dengan halaman web)
@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([permissions.AllowAny])
def leaderboard_api(request):
    period, since = get_period(request)
    leaderboard = get_leaderboard(since)
    top = leaderboard[:10]
    if request.user.is_authenticated:
        rows = [{**row, "is_me": row["user_id"] == request.user.id} for row in top]
        my_rank = next((row for row in leaderboard if row["user_id"] == request.user.id), None)
    else:
        rows = [{"rank": row["rank"], "username": mask_username(row["username"]), "points": row["points"]}
                for row in top]
        my_rank = None
    return Response({
        "period": period,
        "leaderboard": rows,
        "my_rank": my_rank,
        "points_info": [{"label": sources.LABELS[key], "points": point} for key, point in sources.POINTS.items()],
    })
