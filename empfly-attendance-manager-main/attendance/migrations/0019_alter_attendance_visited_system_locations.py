# Generated by Django 4.0.2 on 2022-10-05 04:03

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0018_alter_attendance_visited_system_locations'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attendance',
            name='visited_system_locations',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=100), blank=True, null=True, size=None),
        ),
    ]
