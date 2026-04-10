from django.contrib import admin

from .models import CommunityServiceCategory, CommunityServicePoint


@admin.register(CommunityServiceCategory)
class CommunityServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    ordering = ('sort_order', 'id')


@admin.register(CommunityServicePoint)
class CommunityServicePointAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'status', 'submitted_by', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'address_text', 'detail_description')
    raw_id_fields = ('submitted_by', 'reviewed_by')
    readonly_fields = ('created_at', 'updated_at')
