import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('stores', '0007_storeprofile_is_suspended_by_admin'),
    ]

    operations = [
        migrations.CreateModel(
            name='StoreRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stars', models.PositiveSmallIntegerField(help_text='من 1 إلى 5', verbose_name='النجوم')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'shopper',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='store_ratings',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='المتسوّق',
                    ),
                ),
                (
                    'store',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='ratings',
                        to='stores.storeprofile',
                        verbose_name='المتجر',
                    ),
                ),
            ],
            options={
                'verbose_name': 'تقييم متجر',
                'verbose_name_plural': 'تقييمات المتاجر',
            },
        ),
        migrations.AddConstraint(
            model_name='storerating',
            constraint=models.UniqueConstraint(fields=('store', 'shopper'), name='unique_store_rating_per_shopper'),
        ),
    ]
