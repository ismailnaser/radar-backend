from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0010_store_contact_hours_features'),
    ]

    operations = [
        migrations.AddField(
            model_name='communityservicepoint',
            name='is_hidden_by_admin',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='إن وُضع: لا تظهر النقطة للعامة حتى لو كانت معتمدة (لا يغيّر حالتها).',
                verbose_name='مخفي من الإدارة',
            ),
        ),
    ]

