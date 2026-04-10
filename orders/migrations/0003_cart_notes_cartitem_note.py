from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='cart',
            name='notes',
            field=models.TextField(blank=True, default='', verbose_name='ملاحظات على السلة'),
        ),
        migrations.AddField(
            model_name='cartitem',
            name='note',
            field=models.TextField(blank=True, default='', verbose_name='ملاحظة على المنتج'),
        ),
    ]
