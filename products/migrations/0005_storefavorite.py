# Generated manually

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('stores', '0005_add_electronics_category'),
        ('products', '0004_sponsoredad_payment_receipt_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='StoreFavorite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorited_by_users', to='stores.storeprofile')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='store_favorites', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'متجر مفضّل',
                'verbose_name_plural': 'محلات مفضّلة',
                'unique_together': {('user', 'store')},
            },
        ),
    ]
