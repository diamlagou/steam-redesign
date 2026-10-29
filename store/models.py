from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

REFUND_DAYS = 14
REFUND_HOURS = 2


class Tag(models.Model):
    name = models.CharField("標籤名稱", max_length=30, unique=True)

    class Meta:
        verbose_name = "標籤"
        verbose_name_plural = "標籤"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Game(models.Model):
    RATING_CHOICES = [
        ("G", "普遍級"),
        ("P", "保護級 6+"),
        ("PG12", "輔導級 12+"),
        ("PG15", "輔導級 15+"),
        ("R", "限制級 18+"),
    ]

    name = models.CharField("遊戲名稱", max_length=100)
    description = models.TextField("簡介", blank=True)
    price = models.PositiveIntegerField("原價（NT$）")
    discount = models.PositiveSmallIntegerField("折扣（%）", default=0)
    rating = models.CharField("分級", max_length=4, choices=RATING_CHOICES, default="G")
    supports_zh_tw = models.BooleanField("支援繁體中文", default=True)
    min_players = models.PositiveSmallIntegerField("最少遊玩人數", default=1)
    max_players = models.PositiveSmallIntegerField("最多遊玩人數", default=1)
    os_requirement = models.CharField("作業系統需求", max_length=50, default="Windows 10 以上")
    memory_gb = models.PositiveSmallIntegerField("記憶體需求（GB）", default=8)
    storage_gb = models.PositiveSmallIntegerField("硬碟空間需求（GB）", default=10)
    cover_color = models.CharField("封面顏色", max_length=7, default="#3A7BD5")
    tags = models.ManyToManyField(Tag, verbose_name="標籤", related_name="games", blank=True)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)

    class Meta:
        verbose_name = "遊戲"
        verbose_name_plural = "遊戲"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def final_price(self):
        return self.price * (100 - self.discount) // 100

    @property
    def players_display(self):
        if self.min_players == self.max_players:
            return f"{self.min_players} 人"
        return f"{self.min_players}～{self.max_players} 人"


class Edition(models.Model):
    game = models.ForeignKey(Game, verbose_name="所屬遊戲", on_delete=models.CASCADE, related_name="editions")
    name = models.CharField("版本名稱", max_length=30)
    price = models.PositiveIntegerField("價格（NT$）")
    content = models.TextField("內容說明", blank=True)

    class Meta:
        verbose_name = "版本"
        verbose_name_plural = "版本"
        ordering = ["game", "price"]

    def __str__(self):
        return f"{self.game.name}－{self.name}"


class Library(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="會員", on_delete=models.CASCADE, related_name="library")
    game = models.ForeignKey(Game, verbose_name="遊戲", on_delete=models.CASCADE, related_name="owners")
    purchased_at = models.DateTimeField("購買日期", default=timezone.now)
    playtime_hours = models.DecimalField("遊玩時數", max_digits=6, decimal_places=1, default=0)

    class Meta:
        verbose_name = "收藏庫項目"
        verbose_name_plural = "收藏庫"
        ordering = ["-purchased_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "game"], name="unique_user_game"),
        ]

    def __str__(self):
        return f"{self.user.username}－{self.game.name}"

    @property
    def days_since_purchase(self):
        return (timezone.now() - self.purchased_at).days

    @property
    def refund_deadline(self):
        return self.purchased_at + timedelta(days=REFUND_DAYS)

    @property
    def refund_days_left(self):
        remaining = self.refund_deadline - timezone.now()
        if remaining.total_seconds() <= 0:
            return 0
        return remaining.days + (1 if remaining.seconds else 0)

    @property
    def days_progress(self):
        return min(100, round(self.days_since_purchase / REFUND_DAYS * 100))

    @property
    def hours_progress(self):
        return min(100, round(float(self.playtime_hours) / REFUND_HOURS * 100))

    @property
    def active_refund(self):
        return self.refund_requests.exclude(status="rejected").first()

    @property
    def refund_block_reasons(self):
        reasons = []
        if self.active_refund:
            reasons.append(f"這款遊戲已經申請過退款（{self.active_refund.number}，{self.active_refund.get_status_display()}）。")
        if self.refund_days_left == 0:
            reasons.append(f"購買已超過 {REFUND_DAYS} 天（已購買 {self.days_since_purchase} 天）。")
        if self.playtime_hours >= REFUND_HOURS:
            reasons.append(f"遊玩時數已達 {REFUND_HOURS} 小時以上（目前 {self.playtime_hours} 小時）。")
        return reasons

    @property
    def is_refund_eligible(self):
        return not self.refund_block_reasons


class RefundRequest(models.Model):
    METHOD_CHOICES = [
        ("original", "退回原付款方式"),
        ("wallet", "退回 Steam 錢包"),
    ]
    REASON_CHOICES = [
        ("not_fun", "不好玩"),
        ("performance", "電腦跑不動"),
        ("mistake", "誤買"),
        ("other", "其他"),
    ]
    STATUS_CHOICES = [
        ("pending", "審核中"),
        ("approved", "已核准"),
        ("rejected", "已拒絕"),
    ]

    library_item = models.ForeignKey(Library, verbose_name="收藏庫項目", on_delete=models.CASCADE, related_name="refund_requests")
    method = models.CharField("退款方式", max_length=10, choices=METHOD_CHOICES, default="original")
    reason = models.CharField("原因", max_length=20, choices=REASON_CHOICES)
    note = models.TextField("備註", blank=True)
    created_at = models.DateTimeField("申請時間", auto_now_add=True)
    status = models.CharField("狀態", max_length=10, choices=STATUS_CHOICES, default="pending")

    class Meta:
        verbose_name = "退款申請"
        verbose_name_plural = "退款申請"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number}｜{self.library_item}"

    @property
    def number(self):
        return f"R-{self.pk:05d}"
