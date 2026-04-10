from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0005_add_electronics_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='storeprofile',
            name='location_address',
            field=models.TextField(
                blank=True,
                default='',
                help_text='يُعرض في صفحة المتجر للمتسوّقين، منفصل عن نقطة الخريطة.',
                verbose_name='عنوان / موقع المتجر (نص تفصيلي)',
            ),
        ),
    ]
