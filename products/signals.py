from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .ad_lifecycle import apply_sponsored_ad_expiry_side_effects
from .models import SponsoredAd


@receiver(pre_delete, sender=SponsoredAd)
def sponsored_ad_notify_before_delete(sender, instance, **kwargs):
    """عند حذف إعلان يدوياً (أدمن) نطبق نفس تنظيف السلات والمفضلة."""
    apply_sponsored_ad_expiry_side_effects(instance)
