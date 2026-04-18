from django.db import migrations, models


def forwards_set_flags(apps, schema_editor):
    User = apps.get_model('users', 'CustomUser')
    StoreProfile = apps.get_model('stores', 'StoreProfile')

    User.objects.exclude(user_type='merchant').update(merchant_profile_complete=True)

    for u in User.objects.filter(user_type='merchant'):
        sp = StoreProfile.objects.filter(user_id=u.id).first()
        if not sp:
            continue
        addr = (sp.location_address or '').strip()
        name = (sp.store_name or '').strip()
        has_cat = bool(sp.category_id)
        try:
            if not has_cat and sp.categories.exists():
                has_cat = True
        except Exception:
            pass
        if name and len(addr) >= 5 and has_cat:
            u.merchant_profile_complete = True
            u.save(update_fields=['merchant_profile_complete'])


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_adminwebpushsubscription'),
        ('stores', '0013_storeprofile_categories'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='merchant_profile_complete',
            field=models.BooleanField(
                default=False,
                help_text='للتاجر: هل اكتملت بيانات المتجر الأساسية (اسم، عنوان نصي، قسم)؟',
                verbose_name='اكتمال ملف المتجر',
            ),
        ),
        migrations.RunPython(forwards_set_flags, backwards_noop),
    ]
