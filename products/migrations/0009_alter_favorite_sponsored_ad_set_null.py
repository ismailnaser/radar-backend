import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_sponsoredad_product_favorite_sponsored_ad'),
    ]

    operations = [
        migrations.AlterField(
            model_name='favorite',
            name='sponsored_ad',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='favorite_links',
                to='products.sponsoredad',
            ),
        ),
    ]
