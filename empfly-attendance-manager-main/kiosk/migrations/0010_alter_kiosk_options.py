# Generated by Django 4.0.2 on 2022-10-25 08:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kiosk', '0009_alter_kiosk_unique_together'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='kiosk',
            options={'ordering': ['-updated_at']},
        ),
    ]
