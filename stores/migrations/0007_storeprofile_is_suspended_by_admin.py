# Generated manually for subscription visibility

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0006_storeprofile_location_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='storeprofile',
            name='is_suspended_by_admin',
            field=models.BooleanField(
                default=False,
                help_text='إن وُضع: لا يظهر المتجر للمتسوّقين حتى يُرفع التعليق (يستقل عن الاشتراك).',
                verbose_name='معلّق من الإدارة',
            ),
        ),
    ]
