from django.db import models
from django.conf import settings

class Category(models.Model):
    name = models.CharField("اسم القسم", max_length=100)
    image = models.ImageField("صورة القسم", upload_to='categories/', null=True, blank=True)

    def __str__(self):
        return self.name

class Service(models.Model):
    """قديم — اتركه للبيانات التاريخية؛ العرض العام يستخدم الخدمات المجتمعية."""

    name = models.CharField("نوع الخدمة", max_length=150)
    description = models.TextField("وصف الخدمة", blank=True)
    latitude = models.FloatField("خط العرض", null=True, blank=True)
    longitude = models.FloatField("خط الطول", null=True, blank=True)

    def __str__(self):
        return self.name


class CommunityServiceCategory(models.Model):
    """قسم من أقسام الخدمات المجتمعية — يمكن إضافة أقسام من لوحة Django admin."""

    name = models.CharField("اسم القسم", max_length=200)
    slug = models.SlugField("المعرّف", max_length=80, unique=True)
    image = models.ImageField("صورة القسم", upload_to='community_categories/', null=True, blank=True)
    description_hint = models.TextField(
        "تلميح للمستخدم",
        blank=True,
        help_text="يُعرض عند اقتراح نقطة في هذا القسم.",
    )
    sort_order = models.PositiveSmallIntegerField("ترتيب العرض", default=0)
    is_active = models.BooleanField("نشط", default=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'قسم خدمة مجتمعية'
        verbose_name_plural = 'أقسام الخدمات المجتمعية'

    def __str__(self):
        return self.name


class CommunityServicePoint(models.Model):
    """نقطة خدمة مجتمعية على الخريطة — تظهر للعامة بعد الموافقة."""

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'قيد المراجعة'),
        (STATUS_APPROVED, 'معتمد'),
        (STATUS_REJECTED, 'مرفوض'),
    ]

    INSTITUTION_LOCAL = 'local'
    INSTITUTION_INTERNATIONAL = 'international'
    INSTITUTION_CHARITY = 'charity'
    INSTITUTION_SCOPE_CHOICES = [
        ('', '—'),
        (INSTITUTION_LOCAL, 'محلية'),
        (INSTITUTION_INTERNATIONAL, 'عالمية'),
        (INSTITUTION_CHARITY, 'خيرية'),
    ]

    category = models.ForeignKey(
        CommunityServiceCategory,
        on_delete=models.PROTECT,
        related_name='points',
        verbose_name='القسم',
    )
    title = models.CharField("العنوان / اسم النقطة", max_length=220)
    detail_description = models.TextField("وصف تفصيلي للخدمة")
    latitude = models.FloatField("خط العرض")
    longitude = models.FloatField("خط الطول")
    address_text = models.TextField("الموقع النصي التفصيلي")

    water_is_potable = models.BooleanField(
        "مياه صالحة للشرب",
        null=True,
        blank=True,
        help_text="لقسم نقاط توزيع المياه فقط: هل المياه صالحة للشرب؟",
    )
    institution_scope = models.CharField(
        "نطاق المؤسسة",
        max_length=20,
        choices=INSTITUTION_SCOPE_CHOICES,
        blank=True,
        help_text="لمؤسسات مجتمعية: محلية / عالمية / خيرية.",
    )

    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    is_hidden_by_admin = models.BooleanField(
        "مخفي من الإدارة",
        default=False,
        help_text="إن وُضع: لا تظهر النقطة للعامة حتى لو كانت معتمدة (لا يغيّر حالتها).",
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='community_point_submissions',
        verbose_name='مقدّم الطلب',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='community_points_reviewed',
        verbose_name='راجعه',
    )
    reviewed_at = models.DateTimeField('تاريخ المراجعة', null=True, blank=True)
    rejection_reason = models.TextField('سبب الرفض', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'نقطة خدمة مجتمعية'
        verbose_name_plural = 'نقاط الخدمات المجتمعية'

    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'

class StoreProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='store_profile')
    store_name = models.CharField("اسم المتجر", max_length=200)
    description = models.TextField("وصف المتجر", blank=True)
    logo = models.ImageField("لوغو المتجر", upload_to='store_logos/', null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='stores')
    categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name='stores_multi',
        verbose_name='أقسام المتجر (متعدد)',
        help_text='يمكن اختيار أكثر من قسم للمتجر لظهوره ضمن أكثر من فلتر.',
    )
    latitude = models.FloatField("خط العرض", null=True, blank=True)
    longitude = models.FloatField("خط الطول", null=True, blank=True)
    location_address = models.TextField(
        "عنوان / موقع المتجر (نص تفصيلي)",
        blank=True,
        default='',
        help_text="يُعرض في صفحة المتجر للمتسوّقين، منفصل عن نقطة الخريطة.",
    )
    is_suspended_by_admin = models.BooleanField(
        "معلّق من الإدارة",
        default=False,
        help_text="إن وُضع: لا يظهر المتجر للمتسوّقين حتى يُرفع التعليق (يستقل عن الاشتراك).",
    )
    contact_whatsapp = models.CharField(
        "رقم واتساب للتواصل",
        max_length=24,
        blank=True,
        default='',
        help_text="أرقام مع رمز الدولة بدون + (مثال: 970599123456) لزر التواصل.",
    )
    store_features = models.JSONField(
        "مميزات المتجر (حتى 10)",
        default=list,
        blank=True,
    )
    business_hours_note = models.TextField(
        "مواعيد العمل (نص يظهر للمتسوّقين)",
        blank=True,
        default='',
    )
    business_hours_weekly = models.JSONField(
        "جدول أسبوعي للحساب (أحد=0 … سبت=6)",
        default=dict,
        blank=True,
        help_text='مثال: {"0":[{"start":"09:00","end":"17:00"}],"1":[]}',
    )
    store_timezone = models.CharField(
        "المنطقة الزمنية",
        max_length=64,
        default='Asia/Gaza',
        blank=True,
    )

    def __str__(self):
        return self.store_name


class StoreRating(models.Model):
    """تقييم متجر من 1–5 نجوم؛ متسوّق واحد = تقييم واحد لكل متجر (يُحدَّث عند الإعادة)."""

    store = models.ForeignKey(StoreProfile, on_delete=models.CASCADE, related_name='ratings', verbose_name='المتجر')
    shopper = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='store_ratings',
        verbose_name='المتسوّق',
    )
    stars = models.PositiveSmallIntegerField('النجوم', help_text='من 1 إلى 5')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تقييم متجر'
        verbose_name_plural = 'تقييمات المتاجر'
        constraints = [
            models.UniqueConstraint(
                fields=['store', 'shopper'],
                name='unique_store_rating_per_shopper',
            ),
        ]

    def __str__(self):
        return f'{self.store_id}: {self.stars}⭐ ({self.shopper_id})'
