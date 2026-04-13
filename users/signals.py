from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AdminNotificationEvent
from .views import _send_admin_web_push


@receiver(post_save, sender=AdminNotificationEvent)
def push_admin_notification(sender, instance: AdminNotificationEvent, created: bool, **kwargs):
    if not created:
        return
    # إرسال Push للخلفية
    _send_admin_web_push(instance.title or 'رادار — إشعار', instance.body or '', url='/admin')

