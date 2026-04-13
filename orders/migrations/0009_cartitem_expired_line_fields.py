from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_cartitem_standalone_sponsored_line'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartitem',
            name='is_expired_line',
            field=models.BooleanField(db_index=True, default=False, verbose_name='سطر منتهي الصلاحية'),
        ),
        migrations.AddField(
            model_name='cartitem',
            name='expired_message',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='رسالة انتهاء الصلاحية'),
        ),
    ]

