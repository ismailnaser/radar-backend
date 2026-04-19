from django.core.management import call_command
from django.core.management.base import BaseCommand

from stores.models import StoreProfile


class Command(BaseCommand):
    help = (
        "يشغّل seed_demo تلقائياً عندما لا توجد متاجر في القاعدة "
        "(تثبيت جديد أو قاعدة فارغة)."
    )

    def handle(self, *args, **options):
        if StoreProfile.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "توجد بيانات متاجر بالفعل — لم يُضف شيء. "
                    "لإعادة تعبئة تجريبية استخدم: python manage.py seed_demo --reset"
                )
            )
            return
        self.stdout.write("قاعدة بيانات بدون متاجر — جاري إضافة بيانات تجريبية...")
        call_command("seed_demo", verbosity=1)
