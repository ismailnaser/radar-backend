from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0006_alter_cartitem_sponsored_ad_set_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartitem',
            name='sponsored_unit_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name='سعر القطعة ضمن عرض إعلان ممول (للقطعة الواحدة)',
            ),
        ),
    ]
