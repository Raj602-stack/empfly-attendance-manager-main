# Generated by Django 4.0.2 on 2022-09-16 07:42

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('shift', '0015_rename_is_ism_shiftschedulelog_is_esm'),
    ]

    operations = [
        migrations.AddField(
            model_name='shiftschedulelog',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, unique=True),
        ),
    ]
