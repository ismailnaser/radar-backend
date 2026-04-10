from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_add_is_primary_admin'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='shopper_notices',
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name='إشعارات للمتسوّق (مثلاً بعد إزالة مفضلة بسبب انتهاء إعلان)',
            ),
        ),
    ]
