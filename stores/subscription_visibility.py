"""ظهور متجر التاجر للعامة: تجربة مجانية من تاريخ إنشاء الحساب، ثم اشتراك فعّال."""
from datetime import timedelta

from django.db.models import Exists, OuterRef
from django.utils import timezone

MERCHANT_TRIAL_DAYS = 30
RENEWAL_PERIOD_DAYS = 30

MERCHANT_SUBSCRIPTION_NOTICE_AR = (
    'تحصل اليوم على 30 يوماً مجانية لتجربة عرض متجرك للمتسوقين بشكل كامل! '
    'بعد انتهائها، يتطلب الاستمرار بتفعيل ظهور المتجر دفع رسوم اشتراك شهري.'
)


def trial_end_for_user(user):
    return user.date_joined + timedelta(days=MERCHANT_TRIAL_DAYS)


def store_has_active_paid_window(store):
    """اشتراك نشط وفترة عرض لم تنتهِ بعد."""
    from django.core.exceptions import ObjectDoesNotExist

    try:
        sub = store.subscription
    except ObjectDoesNotExist:
        return False
    now = timezone.now()
    return bool(sub.is_active and sub.end_date and sub.end_date > now)


def store_is_publicly_visible(store):
    if getattr(store, 'is_suspended_by_admin', False):
        return False
    return store_has_active_paid_window(store)


def queryset_public_stores_only(queryset):
    """متاجر تظهر للمتسوّقين على الخريطة والقوائم."""
    from products.models import Subscription

    now = timezone.now()
    active_sub = Subscription.objects.filter(
        store_id=OuterRef('pk'),
        is_active=True,
        end_date__gt=now,
    )
    return queryset.filter(Exists(active_sub), is_suspended_by_admin=False)


def create_trial_subscription_for_store(store):
    """عند التسجيل: نهاية التجربة = تاريخ انضمام صاحب المتجر + 30 يوماً."""
    from products.models import Subscription

    user = store.user
    trial_end = trial_end_for_user(user)
    now = timezone.now()
    return Subscription.objects.create(
        store=store,
        end_date=trial_end,
        is_active=trial_end > now,
    )


def sync_subscription_flags(subscription):
    """يطابق is_active مع انتهاء التاريخ (بدون تمديد تلقائي)."""
    if subscription.end_date and subscription.end_date <= timezone.now():
        if subscription.is_active:
            subscription.is_active = False
            subscription.save(update_fields=['is_active'])
    return subscription


def ensure_subscription_for_store(store):
    """يُنشئ اشتراكاً مربوطاً بتاريخ التسجيل إن لم يوجد، ويحدّث العلم."""
    from products.models import Subscription

    user = store.user
    trial_end = trial_end_for_user(user)
    now = timezone.now()
    sub, _created = Subscription.objects.get_or_create(
        store=store,
        defaults={
            'end_date': trial_end,
            'is_active': trial_end > now,
        },
    )
    return sync_subscription_flags(sub)
