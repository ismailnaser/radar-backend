# -*- coding: utf-8 -*-
from django.db import migrations


def add_electronics_category(apps, schema_editor):
    Category = apps.get_model('stores', 'Category')
    Category.objects.get_or_create(name='إلكترونيات', defaults={})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0004_seed_merchant_categories'),
    ]

    operations = [
        migrations.RunPython(add_electronics_category, noop),
    ]
