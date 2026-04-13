"""دورة حياة الإعلان الممول (انتهاء 24 ساعة)."""
from datetime import timedelta

from django.utils import timezone

from .models import SponsoredAd


def _append_cart_note_sponsored_ended(cart, product_name, catalog_unit_price):
    line = (
        f'انتهت مدة الإعلان الممول للمنتج «{product_name}». '
        f'عُدِّ سعره في السلة إلى السعر الأصلي للمتجر ({catalog_unit_price} ₪) للقطعة الواحدة.'
    )
    prev = (cart.notes or '').strip()
    cart.notes = f'{prev}\n{line}' if prev else line
    cart.save(update_fields=['notes'])


def _append_cart_note_standalone_ad_removed(cart, ad_title):
    line = (
        f'انتهت مدة الإعلان الممول «{ad_title}» (عرض مستقل غير مربوط بمنتج في كتالوج المتجر). '
        f'أُزيل سطر العرض من سلتك تلقائياً لأن السعر كان جزءاً من الإعلان فقط وليس منتجاً دائماً في المتجر.'
    )
    prev = (cart.notes or '').strip()
    cart.notes = f'{prev}\n{line}' if prev else line
    cart.save(update_fields=['notes'])


def _append_shopper_notice(user, message):
    if getattr(user, 'user_type', None) != 'shopper':
        return
    notices = getattr(user, 'shopper_notices', None)
    if not isinstance(notices, list):
        notices = []
    notices = list(notices) + [{'text': message, 'at': timezone.now().isoformat()}]
    user.shopper_notices = notices[-20:]
    user.save(update_fields=['shopper_notices'])


def apply_sponsored_ad_expiry_side_effects(instance):
    """تنظيف السلات والمفضلة عند انتهاء عرض إعلان (قبل حذف السجل أو ترقيته لـ expired)."""
    from orders.models import CartItem

    from .models import Favorite

    for item in CartItem.objects.filter(sponsored_ad=instance).select_related('cart', 'product'):
        if instance.product_id is None:
            cart = item.cart
            _append_cart_note_standalone_ad_removed(cart, instance.title)
            item.product = None
            item.sponsored_ad = None
            item.sponsored_unit_price = None
            item.is_expired_line = True
            item.expired_message = 'انتهت صلاحية الإعلان.'
            item.standalone_line_title = (instance.title or item.standalone_line_title or 'عرض ممول')[:200]
            item.save(update_fields=[
                'product',
                'sponsored_ad',
                'sponsored_unit_price',
                'is_expired_line',
                'expired_message',
                'standalone_line_title',
            ])
        else:
            _append_cart_note_sponsored_ended(item.cart, item.product.name, item.product.price)
            item.sponsored_unit_price = None
            item.save(update_fields=['sponsored_unit_price'])

    for fav in Favorite.objects.filter(sponsored_ad=instance).select_related('user', 'product'):
        if instance.product_id is None:
            _append_shopper_notice(
                fav.user,
                (
                    f'انتهت مدة الإعلان الممول «{instance.title}» (عرض مستقل غير مربوط بمنتج في كتالوج المتجر). '
                    f'أُزيل من مفضلتك لأن العرض لم يعد متاحاً.'
                ),
            )
            fav.delete()
        else:
            _append_shopper_notice(
                fav.user,
                (
                    f'انتهت مدة الإعلان الممول لـ «{fav.product.name}». '
                    f'المنتج ما زال في مفضلتك كمنتج من المتجر.'
                ),
            )
            fav.sponsored_ad = None
            fav.save(update_fields=['sponsored_ad'])


def purge_expired_sponsored_ads():
    """إعلانات نشطة تجاوزت 24 ساعة من الموافقة: نفس آثار الحذف على السلات، ثم ترقية الحالة إلى منتهي."""
    cutoff = timezone.now() - timedelta(hours=24)
    qs = list(SponsoredAd.objects.filter(status='active', approved_at__lt=cutoff))
    for ad in qs:
        apply_sponsored_ad_expiry_side_effects(ad)
        ad.status = 'expired'
        ad.save(update_fields=['status'])
