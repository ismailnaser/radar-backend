import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_sponsoredad_product_favorite_sponsored_ad'),
        ('orders', '0004_cart_share_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartitem',
            name='sponsored_ad',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='cart_items',
                to='products.sponsoredad',
            ),
        ),
    ]
