import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

class CustomUserManager(BaseUserManager):
    def create_user(self, username, phone_number=None, password=None, **extra_fields):
        if not username:
            raise ValueError("اسم المستخدم مطلوب")
        if not phone_number or not str(phone_number).strip():
            phone_number = f"r{uuid.uuid4().hex[:18]}"
        user = self.model(username=username, phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'admin')
        extra_fields.setdefault('is_primary_admin', True)

        return self.create_user(username, phone_number, password, **extra_fields)


class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('shopper', 'متسوق'),
        ('merchant', 'تاجر'),
        ('admin', 'مدير النظام'),
    )
    phone_number = models.CharField("رقم الهاتف", max_length=20, unique=True)
    user_type = models.CharField("نوع الحساب", max_length=15, choices=USER_TYPE_CHOICES, default='shopper')
    is_primary_admin = models.BooleanField(
        "مدير أساسي",
        default=False,
        help_text="المدير الأساسي فقط يدير حسابات المدراء الآخرين من لوحة الإدارة. المدير الفرعي يراجع الإعلانات والاشتراكات فقط.",
    )
    is_whatsapp_verified = models.BooleanField("تم التحقق من الواتساب", default=False)
    otp_code = models.CharField("رمز التحقق", max_length=6, null=True, blank=True)
    otp_expiry = models.DateTimeField("تاريخ انتهاء الرمز", null=True, blank=True)
    shopper_notices = models.JSONField(
        "إشعارات للمتسوّق (مثلاً بعد إزالة مفضلة بسبب انتهاء إعلان)",
        default=list,
        blank=True,
    )

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['phone_number']

    objects = CustomUserManager()

    class Meta(AbstractUser.Meta):
        verbose_name = _('مستخدم')
        verbose_name_plural = _('المستخدمون')

    def __str__(self):
        return f"{self.username} ({self.phone_number})"


class AppOpenStat(models.Model):
    """عداد بسيط لفتح التطبيق (مرة لكل تحميل SPA)."""

    date = models.DateField("التاريخ", unique=True, db_index=True)
    open_count = models.PositiveIntegerField("عدد الفتحات", default=0)

    class Meta:
        verbose_name = "إحصاء فتح التطبيق"
        verbose_name_plural = "إحصاءات فتح التطبيق"

    def __str__(self):
        return f"{self.date}: {self.open_count}"


class SiteAnnouncement(models.Model):
    """إعلان عام يظهر لجميع المستخدمين داخل الواجهة."""

    message = models.TextField("نص الإعلان")
    is_active = models.BooleanField("نشط", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="site_announcements",
        verbose_name="أنشئ بواسطة",
    )

    class Meta:
        verbose_name = "إعلان عام"
        verbose_name_plural = "إعلانات عامة"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        msg = (self.message or "").strip()
        return (msg[:40] + "…") if len(msg) > 40 else (msg or "—")


class AdminNotificationEvent(models.Model):
    """أحداث بسيطة لإشعارات المدراء داخل التطبيق (in-app).

    الهدف: وصول إشعار عند إنشاء طلب إعلان ممول/تجديد اشتراك/اقتراح خدمة مجتمعية.
    """

    TYPE_AD_REQUEST = "ad_request"
    TYPE_SUBSCRIPTION_RENEWAL = "subscription_renewal"
    TYPE_COMMUNITY_POINT = "community_point"
    TYPE_CHOICES = [
        (TYPE_AD_REQUEST, "طلب إعلان ممول"),
        (TYPE_SUBSCRIPTION_RENEWAL, "طلب تجديد اشتراك"),
        (TYPE_COMMUNITY_POINT, "طلب خدمة مجتمعية"),
    ]

    event_type = models.CharField("نوع الحدث", max_length=40, choices=TYPE_CHOICES, db_index=True)
    title = models.CharField("عنوان", max_length=200)
    body = models.TextField("وصف", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_notification_events_created",
        verbose_name="أنشئ بواسطة",
    )

    # روابط اختيارية كي نعرض "افتح الطلب" لاحقاً
    related_app = models.CharField("التطبيق", max_length=32, blank=True, default="")
    related_id = models.PositiveIntegerField("المعرّف", null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "إشعار إداري"
        verbose_name_plural = "إشعارات إدارية"

    def __str__(self):
        return f"{self.event_type}: {self.title}"
