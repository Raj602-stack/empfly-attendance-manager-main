# Generated by Django 4.0.2 on 2022-10-29 06:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shift', '0045_alter_shift_default_location'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='locationsettings',
            options={'ordering': ['-applicable_start_date']},
        ),
        migrations.AlterModelOptions(
            name='shift',
            options={'ordering': ['-updated_at']},
        ),
    ]
