from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db.models import ExpressionWrapper, F, IntegerField, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import RefundForm
from .models import Game, Library, RefundRequest, Tag

PLAYER_CHOICES = [
    ("solo", "單人可玩"),
    ("2", "可 2 人一起玩"),
    ("4plus", "可 4 人以上"),
]

PRICE_CHOICES = [
    ("free", "免費"),
    ("u500", "NT$500 以下"),
    ("500to1000", "NT$500～1,000"),
]


def index(request):
    sale_games = Game.objects.filter(discount__gt=0).prefetch_related("tags")
    context = {
        "sale_games": sale_games,
        "total_games": Game.objects.count(),
        "all_tags": Tag.objects.all(),
        "price_choices": PRICE_CHOICES,
    }
    return render(request, "store/index.html", context)


def remove_param_url(request, key, value=None):
    params = request.GET.copy()
    if value is None:
        params.pop(key, None)
    else:
        params.setlist(key, [v for v in params.getlist(key) if v != value])
    query = params.urlencode()
    return f"{reverse('search')}?{query}" if query else reverse("search")


def search(request):
    games = Game.objects.annotate(
        final=ExpressionWrapper(
            F("price") * (100 - F("discount")) / 100,
            output_field=IntegerField(),
        )
    ).prefetch_related("tags")

    q = request.GET.get("q", "").strip()
    zh = request.GET.get("zh") == "1"
    tag_ids = [t for t in request.GET.getlist("tag") if t.isdigit()]
    players = request.GET.get("players", "")
    price = request.GET.get("price", "")
    sale = request.GET.get("sale") == "1"

    applied = []

    if q:
        games = games.filter(Q(name__icontains=q) | Q(description__icontains=q))
        applied.append((f"關鍵字：{q}", remove_param_url(request, "q")))

    if zh:
        games = games.filter(supports_zh_tw=True)
        applied.append(("繁體中文", remove_param_url(request, "zh")))

    selected_tags = Tag.objects.filter(id__in=tag_ids)
    for tag in selected_tags:
        games = games.filter(tags=tag)
        applied.append((tag.name, remove_param_url(request, "tag", str(tag.id))))

    if players == "solo":
        games = games.filter(min_players__lte=1)
    elif players == "2":
        games = games.filter(min_players__lte=2, max_players__gte=2)
    elif players == "4plus":
        games = games.filter(max_players__gte=4)
    if players in dict(PLAYER_CHOICES):
        applied.append((dict(PLAYER_CHOICES)[players], remove_param_url(request, "players")))

    if price == "free":
        games = games.filter(final=0)
    elif price == "u500":
        games = games.filter(final__lte=500)
    elif price == "500to1000":
        games = games.filter(final__gte=500, final__lte=1000)
    if price in dict(PRICE_CHOICES):
        applied.append((dict(PRICE_CHOICES)[price], remove_param_url(request, "price")))

    if sale:
        games = games.filter(discount__gt=0)
        applied.append(("只看特價", remove_param_url(request, "sale")))

    games = games.distinct()

    context = {
        "games": games,
        "result_count": games.count(),
        "total_games": Game.objects.count(),
        "applied": applied,
        "q": q,
        "zh": zh,
        "all_tags": Tag.objects.all(),
        "selected_tags": [int(t) for t in tag_ids],
        "players": players,
        "price": price,
        "sale": sale,
        "player_choices": PLAYER_CHOICES,
        "price_choices": PRICE_CHOICES,
    }
    return render(request, "store/search.html", context)


def game_detail(request, pk):
    game = get_object_or_404(Game.objects.prefetch_related("tags", "editions"), pk=pk)
    owned = False
    if request.user.is_authenticated:
        owned = (
            Library.objects.filter(user=request.user, game=game)
            .exclude(refund_requests__status="approved")
            .exists()
        )
    return render(request, "store/game.html", {"game": game, "owned": owned})


@login_required
@require_POST
def add_to_library(request, pk):
    game = get_object_or_404(Game, pk=pk)
    item, created = Library.objects.get_or_create(user=request.user, game=game)
    if not created and item.refund_requests.filter(status="approved").exists():
        messages.info(request, f"「{game.name}」已經退款，無法再次加入收藏庫。")
        return redirect("game_detail", pk=game.pk)
    if created:
        messages.success(request, f"已將「{game.name}」加入收藏庫。")
    else:
        messages.info(request, f"「{game.name}」已經在你的收藏庫裡。")
    return redirect("library")


@login_required
def library(request):
    items = (
        Library.objects.filter(user=request.user)
        .exclude(refund_requests__status="approved")
        .select_related("game")
    )
    return render(request, "store/library.html", {"items": items})


def signup(request):
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"註冊成功，歡迎 {user.username}！")
            return redirect("index")
    else:
        form = UserCreationForm()

    return render(request, "store/signup.html", {"form": form})


@login_required
def refund_request(request, pk):
    item = get_object_or_404(Library.objects.select_related("game"), pk=pk, user=request.user)

    if request.method == "POST" and not item.is_refund_eligible:
        messages.error(request, "這款遊戲目前不符合退款資格，無法送出申請。")
        return redirect("refund_request", pk=item.pk)

    form = RefundForm(request.POST or None)
    step = request.POST.get("step")

    if request.method == "POST" and step in ("confirm", "submit") and form.is_valid():
        if step == "submit":
            refund = form.save(commit=False)
            refund.library_item = item
            refund.save()
            return redirect("refund_done", pk=refund.pk)

        return render(request, "store/refund_confirm.html", {"item": item, "form": form, "data": form.cleaned_data})

    return render(request, "store/refund.html", {"item": item, "form": form})


@login_required
def refund_done(request, pk):
    refund = get_object_or_404(
        RefundRequest.objects.select_related("library_item__game"),
        pk=pk,
        library_item__user=request.user,
    )
    return render(request, "store/refund_done.html", {"refund": refund})
