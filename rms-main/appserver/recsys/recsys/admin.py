from django.contrib import admin
from recsys.models import HotPaper, ColdKeyword, Ad, Subject, ChineseEnglish, ChatRound


@admin.register(HotPaper)
class HotPaperAdmin(admin.ModelAdmin):
    exclude = ["create_at", "modify_at"]
    list_display = ["pub_id", "pub_topic_id", "is_top", "display_device", "top_start_at", "top_end_at", "top_reason_zh", "top_reason_en", "create_at", "modify_at"]


@admin.register(ColdKeyword)
class ColdKeywordAdmin(admin.ModelAdmin):
    exclude = ["create_at", "modify_at"]
    list_display = ["word", "create_at", "modify_at"]


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    exclude = ["create_at", "modify_at"]
    list_display = ['title', 'title_zh', 'keywords', 'url', 'author_ids', 'total', 'desc', 'desc_zh', "create_at", "modify_at"]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    exclude = ["create_at", "modify_at"]
    list_display = ['title', 'title_zh', 'keywords', 'keywords_zh', "create_at", "modify_at"]


@admin.register(ChineseEnglish)
class ChEnAdmin(admin.ModelAdmin):
    list_display = ["ch", "eng", "translator", "create_at"]


@admin.register(ChatRound) 
class ChatRoundAdmin(admin.ModelAdmin):
    list_display = [
        "create_at", 'uid', "user_message", "assistant_message", 
        "assistant_extend_message", "pub_titles", "spend_seconds", "extend_spend_seconds"
    ]