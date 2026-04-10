from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_customuser_shopper_notices'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppOpenStat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True, unique=True)),
                ('open_count', models.PositiveIntegerField(default=0)),
            ],
        ),
    ]

