# -*- coding: utf-8 -*-
from django.db import migrations


def add_spices_category(apps, schema_editor):
    Category = apps.get_model('stores', 'Category')
    Category.objects.get_or_create(name='عطارة وبهارات', defaults={})


def remove_spices_category(apps, schema_editor):
    Category = apps.get_model('stores', 'Category')
    Category.objects.filter(name='عطارة وبهارات').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('stores', '0013_storeprofile_categories'),
    ]

    operations = [
        migrations.RunPython(add_spices_category, remove_spices_category),
    ]

