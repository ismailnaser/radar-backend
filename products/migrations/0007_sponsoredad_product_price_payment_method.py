from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0006_sponsored_ad_approved_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='sponsoredad',
            name='product_price',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0'),
                max_digits=10,
                verbose_name='سعر المنتج المعروض في الإعلان',
            ),
        ),
        migrations.AddField(
            model_name='sponsoredad',
            name='payment_method',
            field=models.CharField(
                choices=[('balipay_wallet', 'محفظة بال باي'), ('bank_palestine', 'بنك فلسطين')],
                default='balipay_wallet',
                max_length=20,
                verbose_name='قناة الدفع',
            ),
        ),
    ]
