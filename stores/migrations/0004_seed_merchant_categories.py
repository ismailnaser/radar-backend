# -*- coding: utf-8 -*-
from django.db import migrations

# أسماء أقسام التجار كما في نموذج التسجيل (ملابس = ثلاثة أقسام منفصلة في قاعدة البيانات)
CATEGORY_NAMES = [
    'ميني مول',
    'سوبر ماركت',
    'خضار و فواكه',
    'ملحمة',
    'حلويات',
    'مطعم',
    'كافيه',
    'مساحات عمل',
    'صيدلية',
    'أدوات منزلية',
    'أدوات كهربائية',
    'أدوات بناء',
    'ملابس نسائي',
    'ملابس رجالي',
    'ملابس أطفال',
    'أحذية',
    'كوزماتكس',
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('stores', 'Category')
    for name in CATEGORY_NAMES:
        Category.objects.get_or_create(name=name, defaults={})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0003_storeprofile_logo'),
    ]

    operations = [
        migrations.RunPython(seed_categories, noop),
    ]
