# Generated by Django 4.0.2 on 2022-09-23 09:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shift', '0025_rename_location_start_time_restriction_shift_loc_settings_start_time_restriction'),
    ]

    operations = [
        migrations.AddField(
            model_name='shift',
            name='status',
            field=models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active', max_length=50),
        ),
    ]
