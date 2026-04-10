from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0012_favorite_standalone_ad'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sponsoredad',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'قيد الانتظار'),
                    ('active', 'نشط'),
                    ('rejected', 'مرفوض'),
                    ('expired', 'منتهي الصلاحية'),
                ],
                default='pending',
                max_length=20,
                verbose_name='حالة الإعلان',
            ),
        ),
    ]
