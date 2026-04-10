import uuid
from django.db import migrations, models


def fill_share_tokens(apps, schema_editor):
    Cart = apps.get_model('orders', 'Cart')
    for row in Cart.objects.all():
        row.share_token = uuid.uuid4()
        row.save(update_fields=['share_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_cart_notes_cartitem_note'),
    ]

    operations = [
        migrations.AddField(
            model_name='cart',
            name='share_token',
            field=models.UUIDField(editable=False, null=True, verbose_name='رمز مشاركة السلة'),
        ),
        migrations.RunPython(fill_share_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='cart',
            name='share_token',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True, verbose_name='رمز مشاركة السلة'),
        ),
    ]
