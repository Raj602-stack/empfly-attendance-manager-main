# Generated by Django 4.0.2 on 2022-09-23 06:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shift', '0022_remove_locationsettings_end_time_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='locationsettings',
            name='end_time',
            field=models.TimeField(default='06:46:39'),
        ),
    ]
