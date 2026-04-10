import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from products.models import Product, SponsoredAd
from stores.models import StoreProfile

class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='carts')
    name = models.CharField("اسم السلة", max_length=100, default="سلة المشتريات")
    notes = models.TextField("ملاحظات على السلة", blank=True, default='')
    share_token = models.UUIDField(
        "رمز مشاركة السلة",
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.phone_number} - {self.name}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    standalone_line_title = models.CharField(
        'عنوان سطر إعلان مستقل',
        max_length=200,
        blank=True,
        default='',
    )
    sponsored_ad = models.ForeignKey(
        SponsoredAd,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cart_items',
    )
    sponsored_unit_price = models.DecimalField(
        "سعر القطعة ضمن عرض إعلان ممول (للقطعة الواحدة)",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField("الكمية", default=1)
    note = models.TextField("ملاحظة على المنتج", blank=True, default='')

    @property
    def effective_unit_price(self):
        if self.sponsored_unit_price is not None:
            return self.sponsored_unit_price
        if self.product_id:
            return self.product.price
        return self.sponsored_unit_price if self.sponsored_unit_price is not None else Decimal('0')

    @property
    def line_total_effective(self):
        return self.effective_unit_price * self.quantity

    @property
    def is_promotional_line(self):
        return self.sponsored_unit_price is not None

    def __str__(self):
        label = self.product.name if self.product_id else (self.standalone_line_title or 'عرض')
        return f'{self.quantity} × {label}'

class VisitorStat(models.Model):
    store = models.ForeignKey(StoreProfile, on_delete=models.CASCADE, related_name='stats')
    date = models.DateField(auto_now_add=True)
    visitor_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ('store', 'date')

    def __str__(self):
        return f"زوار {self.store.store_name} - {self.date}"
