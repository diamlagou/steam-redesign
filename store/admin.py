from django.contrib import admin, messages

from .models import Edition, Game, Library, RefundRequest, Tag

admin.site.site_header = "第16組 Steam Redesign 管理後台"
admin.site.site_title = "Steam Redesign 管理後台"
admin.site.index_title = "資料管理"


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "game_count"]
    search_fields = ["name"]

    @admin.display(description="遊戲數量")
    def game_count(self, obj):
        return obj.games.count()


class EditionInline(admin.TabularInline):
    model = Edition
    extra = 1


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "discount", "sale_price", "rating", "supports_zh_tw", "players", "tag_list"]
    list_display_links = ["name"]
    list_editable = ["discount"]
    list_filter = ["tags", "rating", "supports_zh_tw"]
    search_fields = ["name", "description"]
    filter_horizontal = ["tags"]
    inlines = [EditionInline]
    fieldsets = [
        ("基本資料", {"fields": ["name", "description", "tags", "cover_color"]}),
        ("價格", {"fields": ["price", "discount"]}),
        ("購買前重點", {"fields": ["rating", "supports_zh_tw", "min_players", "max_players"]}),
        ("電腦需求", {"fields": ["os_requirement", "memory_gb", "storage_gb"]}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("tags")

    @admin.display(description="折扣後價格")
    def sale_price(self, obj):
        return obj.final_price

    @admin.display(description="遊玩人數")
    def players(self, obj):
        return obj.players_display

    @admin.display(description="標籤")
    def tag_list(self, obj):
        return "、".join(tag.name for tag in obj.tags.all())


@admin.register(Edition)
class EditionAdmin(admin.ModelAdmin):
    list_display = ["game", "name", "price"]
    list_filter = ["game"]
    search_fields = ["game__name", "name"]


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ["user", "game", "purchased_at", "playtime_hours", "refund_status"]
    list_filter = ["user", "game"]
    search_fields = ["user__username", "game__name"]
    list_select_related = ["user", "game"]
    date_hierarchy = "purchased_at"

    @admin.display(description="退款狀態")
    def refund_status(self, obj):
        refund = obj.active_refund
        if refund:
            return f"{refund.number} {refund.get_status_display()}"
        if obj.is_refund_eligible:
            return f"可退款（剩 {obj.refund_days_left} 天）"
        return "不可退款"


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ["number", "applicant", "game", "reason", "method", "status", "created_at"]
    list_display_links = ["number"]
    list_filter = ["status", "reason", "method"]
    search_fields = ["library_item__user__username", "library_item__game__name", "note"]
    list_select_related = ["library_item__user", "library_item__game"]
    readonly_fields = ["created_at"]
    actions = ["approve_requests", "reject_requests"]

    @admin.display(description="申請編號", ordering="id")
    def number(self, obj):
        return obj.number

    @admin.display(description="申請人", ordering="library_item__user__username")
    def applicant(self, obj):
        return obj.library_item.user.username

    @admin.display(description="遊戲", ordering="library_item__game__name")
    def game(self, obj):
        return obj.library_item.game.name

    @admin.action(description="將選取的申請改為「已核准」")
    def approve_requests(self, request, queryset):
        updated = queryset.update(status="approved")
        self.message_user(request, f"已核准 {updated} 筆退款申請。", messages.SUCCESS)

    @admin.action(description="將選取的申請改為「已拒絕」")
    def reject_requests(self, request, queryset):
        updated = queryset.update(status="rejected")
        self.message_user(request, f"已拒絕 {updated} 筆退款申請。", messages.WARNING)
