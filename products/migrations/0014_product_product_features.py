from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0013_sponsoredad_status_expired'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='product_features',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='قائمة قصيرة (مثل: المقاس، اللون، الخامة...). اختيارية وتظهر للمتسوقين.',
                verbose_name='تفاصيل المنتج (حتى 5)',
            ),
        ),
    ]

