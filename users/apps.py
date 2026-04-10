from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    verbose_name = _('حسابات المستخدمين')

    def ready(self):
        # تحميل تسجيل الأدمن مع التطبيق (يعتمد django أيضاً على autodiscover)
        import users.admin  # noqa: F401
