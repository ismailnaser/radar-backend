import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_cartitem_sponsored_ad'),
        ('products', '0009_alter_favorite_sponsored_ad_set_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cartitem',
            name='sponsored_ad',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cart_items',
                to='products.sponsoredad',
            ),
        ),
    ]
