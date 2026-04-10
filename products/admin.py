from django.contrib import admin
from .models import Product, SponsoredAd, Subscription, Favorite, StoreFavorite, SubscriptionRenewalRequest

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "store", "price", "is_archived", "created_at")
    list_filter = ("is_archived", "created_at")
    search_fields = ("name", "store__store_name")


@admin.register(SponsoredAd)
class SponsoredAdAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "store",
        "product",
        "product_price",
        "payment_method",
        "status",
        "approved_at",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("title", "store__store_name")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "store", "end_date", "is_active", "start_date")
    list_filter = ("is_active",)
    search_fields = ("store__store_name",)


@admin.register(SubscriptionRenewalRequest)
class SubscriptionRenewalRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "store", "status", "created_at", "decided_at")
    list_filter = ("status", "created_at")
    search_fields = ("store__store_name",)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "product", "sponsored_ad", "created_at")
    search_fields = ("user__username", "product__name", "sponsored_ad__title")


@admin.register(StoreFavorite)
class StoreFavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "store", "created_at")
    search_fields = ("user__username", "store__store_name")

# Register your models here.
