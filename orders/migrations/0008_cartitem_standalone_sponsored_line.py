from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_cartitem_sponsored_unit_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartitem',
            name='standalone_line_title',
            field=models.CharField(
                blank=True,
                default='',
                max_length=200,
                verbose_name='عنوان سطر إعلان مستقل',
            ),
        ),
        migrations.AlterField(
            model_name='cartitem',
            name='product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='products.product',
            ),
        ),
    ]
