# Generated by Django 4.0.2 on 2022-09-16 05:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shift', '0013_shiftschedulelog_organization_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='shiftschedulelog',
            old_name='is_employee_shift_mapping',
            new_name='is_ism',
        ),
    ]
