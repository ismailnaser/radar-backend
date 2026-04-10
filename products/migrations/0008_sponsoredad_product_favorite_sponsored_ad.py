import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_sponsoredad_product_price_payment_method'),
    ]

    operations = [
        migrations.AddField(
            model_name='sponsoredad',
            name='product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sponsored_ads',
                to='products.product',
                verbose_name='المنتج المعروض في الإعلان',
            ),
        ),
        migrations.AddField(
            model_name='favorite',
            name='sponsored_ad',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='favorite_links',
                to='products.sponsoredad',
            ),
        ),
    ]
