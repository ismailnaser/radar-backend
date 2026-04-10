from django.db import models
from django.conf import settings
from stores.models import StoreProfile
from django.utils import timezone
from datetime import timedelta

class Product(models.Model):
    store = models.ForeignKey(StoreProfile, on_delete=models.CASCADE, related_name='products')
    name = models.CharField("اسم المنتج", max_length=200)
    price = models.DecimalField("السعر", max_digits=10, decimal_places=2)
    description = models.TextField("وصف المنتج", blank=True, null=True)
    product_features = models.JSONField(
        "تفاصيل المنتج (حتى 5)",
        default=list,
        blank=True,
        help_text="قائمة قصيرة (مثل: المقاس، اللون، الخامة...). اختيارية وتظهر للمتسوقين.",
    )
    image = models.ImageField("صورة المنتج", upload_to='products/', null=True, blank=True)
    is_archived = models.BooleanField("مؤرشف", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ProductGalleryImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='products/gallery/')
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.product_id}:{self.sort_order}'


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites')
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        null=True,
        blank=True,
    )
    sponsored_ad = models.ForeignKey(
        'SponsoredAd',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='favorite_links',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "المفضلة"
        verbose_name_plural = "المفضلات"
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'product'),
                condition=models.Q(product__isnull=False),
                name='favorite_user_product_uniq',
            ),
            models.UniqueConstraint(
                fields=('user', 'sponsored_ad'),
                condition=models.Q(product__isnull=True, sponsored_ad__isnull=False),
                name='favorite_user_standalone_ad_uniq',
            ),
        ]

    def __str__(self):
        if self.product_id:
            return f"{self.user.phone_number} - {self.product.name}"
        return f"{self.user.phone_number} - إعلان: {getattr(self.sponsored_ad, 'title', '—')}"


class StoreFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='store_favorites')
    store = models.ForeignKey(StoreProfile, on_delete=models.CASCADE, related_name='favorited_by_users')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'store')
        verbose_name = "متجر مفضّل"
        verbose_name_plural = "محلات مفضّلة"

    def __str__(self):
        return f"{self.user.phone_number} - {self.store.store_name}"

class SponsoredAd(models.Model):
    PAYMENT_BALIPAY = 'balipay_wallet'
    PAYMENT_BANK_PS = 'bank_palestine'
    PAYMENT_OTHER = 'other'
    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_BALIPAY, 'محفظة بال باي'),
        (PAYMENT_BANK_PS, 'بنك فلسطين'),
        (PAYMENT_OTHER, 'أخرى'),
    ]

    store = models.ForeignKey(StoreProfile, on_delete=models.CASCADE, related_name='ads')
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sponsored_ads',
        verbose_name='المنتج المعروض في الإعلان',
    )
    title = models.CharField("عنوان الإعلان", max_length=200)
    description = models.TextField("تفاصيل الإعلان", blank=True, default='')
    product_price = models.DecimalField(
        "سعر المنتج المعروض في الإعلان",
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    payment_method = models.CharField(
        "قناة الدفع",
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_BALIPAY,
    )
    image = models.ImageField("صورة الإعلان", upload_to='ads/', null=True, blank=True)
    payment_receipt_image = models.ImageField("إشعار دفع الإعلان", upload_to='ad_receipts/', null=True, blank=True)
    status = models.CharField("حالة الإعلان", max_length=20, default='pending', choices=[
        ('pending', 'قيد الانتظار'),
        ('active', 'نشط'),
        ('rejected', 'مرفوض'),
        ('expired', 'منتهي الصلاحية'),
    ])
    approved_at = models.DateTimeField("وقت الموافقة (بداية الظهور 24 ساعة)", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class SponsoredAdGalleryImage(models.Model):
    sponsored_ad = models.ForeignKey(SponsoredAd, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='ads/gallery/')
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.sponsored_ad_id}:{self.sort_order}'


class Subscription(models.Model):
    store = models.OneToOneField(StoreProfile, on_delete=models.CASCADE, related_name='subscription')
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField("تاريخ الانتهاء")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"اشتراك {self.store.store_name}"


class SubscriptionRenewalRequest(models.Model):
    PAYMENT_BALIPAY = 'balipay_wallet'
    PAYMENT_BANK_PS = 'bank_palestine'
    PAYMENT_OTHER = 'other'
    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_BALIPAY, 'محفظة بال باي'),
        (PAYMENT_BANK_PS, 'بنك فلسطين'),
        (PAYMENT_OTHER, 'أخرى'),
    ]

    store = models.ForeignKey(StoreProfile, on_delete=models.CASCADE, related_name='subscription_renewal_requests')
    receipt_image = models.ImageField("إشعار الدفع", upload_to='subscription_receipts/')
    notes = models.TextField("ملاحظات", blank=True, null=True)
    payment_method = models.CharField(
        "قناة الدفع",
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_OTHER,
    )
    amount_ils = models.DecimalField(
        "قيمة التحويل (شيكل)",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="اختياري: تُستخدم لحساب أرباح المشروع.",
    )
    status = models.CharField("حالة الطلب", max_length=20, default='pending', choices=[
        ('pending', 'قيد الانتظار'),
        ('approved', 'مقبول'),
        ('rejected', 'مرفوض'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(blank=True, null=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='decided_subscription_renewal_requests',
    )

    def __str__(self):
        return f"تجديد اشتراك - {self.store.store_name} ({self.status})"

    def approve(self, decided_by=None, days=30):
        subscription, created = Subscription.objects.get_or_create(
            store=self.store,
            defaults={
                "end_date": timezone.now() + timedelta(days=days),
                "is_active": True,
            },
        )
        now = timezone.now()
        base = subscription.end_date if subscription.end_date and subscription.end_date > now else now
        subscription.end_date = base + timedelta(days=days)
        subscription.is_active = True
        subscription.save(update_fields=["end_date", "is_active"])

        self.status = "approved"
        self.decided_at = now
        self.decided_by = decided_by
        self.save(update_fields=["status", "decided_at", "decided_by"])

    def reject(self, decided_by=None):
        now = timezone.now()
        self.status = "rejected"
        self.decided_at = now
        self.decided_by = decided_by
        self.save(update_fields=["status", "decided_at", "decided_by"])


class FinanceTransfer(models.Model):
    """سجل أرباح/تحويلات النظام (إعلان ممول أو تجديد اشتراك مقبول)."""

    KIND_AD = "sponsored_ad"
    KIND_SUBSCRIPTION_RENEWAL = "subscription_renewal"
    KIND_CHOICES = [
        (KIND_AD, "إعلان ممول"),
        (KIND_SUBSCRIPTION_RENEWAL, "تجديد اشتراك"),
    ]

    PAYMENT_BALIPAY = SponsoredAd.PAYMENT_BALIPAY
    PAYMENT_BANK_PS = SponsoredAd.PAYMENT_BANK_PS
    PAYMENT_OTHER = SponsoredAd.PAYMENT_OTHER
    PAYMENT_METHOD_CHOICES = SponsoredAd.PAYMENT_METHOD_CHOICES

    kind = models.CharField("نوع التحويل", max_length=30, choices=KIND_CHOICES, db_index=True)
    store = models.ForeignKey(StoreProfile, on_delete=models.CASCADE, related_name="finance_transfers")
    payment_method = models.CharField("قناة الدفع", max_length=20, choices=PAYMENT_METHOD_CHOICES, default=PAYMENT_OTHER, db_index=True)
    amount_ils = models.DecimalField("المبلغ (شيكل)", max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    sponsored_ad = models.OneToOneField(
        SponsoredAd,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="finance_transfer",
    )
    subscription_renewal = models.OneToOneField(
        SubscriptionRenewalRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="finance_transfer",
    )

    class Meta:
        verbose_name = "تحويل مالي"
        verbose_name_plural = "تحويلات مالية"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.amount_ils}₪ — {self.store_id}"
