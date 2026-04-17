from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import os
import logging


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    verbose_name = _('حسابات المستخدمين')

    def ready(self):
        # تحميل تسجيل الأدمن مع التطبيق (يعتمد django أيضاً على autodiscover)
        import users.admin  # noqa: F401
        import users.signals  # noqa: F401

        # Ensure django.contrib.sites has a sane domain in production.
        # This prevents allauth from failing when Site row is missing/mismatched.
        logger = logging.getLogger(__name__)
        try:
            from django.contrib.sites.models import Site
            from django.db.utils import OperationalError, ProgrammingError

            site_id = getattr(settings, "SITE_ID", 1)
            domain = (os.environ.get("SITE_DOMAIN") or "").strip()
            if not domain:
                # Prefer the known DO app domain if present in ALLOWED_HOSTS
                for h in (getattr(settings, "ALLOWED_HOSTS", []) or []):
                    if h and h not in ("localhost", "127.0.0.1", "::1", "testserver"):
                        domain = str(h).strip()
                        break
            if not domain:
                domain = "radar-rbvob.ondigitalocean.app"

            Site.objects.update_or_create(
                id=site_id,
                defaults={"domain": domain, "name": domain},
            )
        except (OperationalError, ProgrammingError):
            # Most likely migrations haven't run yet (django_site table missing).
            logger.exception("Sites table not ready (did you run migrate for django.contrib.sites?)")
        except Exception:
            logger.exception("Failed to ensure Site domain during startup")
