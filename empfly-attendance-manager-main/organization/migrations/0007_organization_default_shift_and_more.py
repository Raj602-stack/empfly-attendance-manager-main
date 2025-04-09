# Generated by Django 4.0.2 on 2022-09-03 10:43

from django.db import migrations, models
import django.db.models.deletion
import organization.models


class Migration(migrations.Migration):

    dependencies = [
        ('shift', '0003_alter_shift_unique_together'),
        ('organization', '0006_organizationlocation_enable_visitation'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='default_shift',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='shift.shift'),
        ),
        migrations.AddField(
            model_name='organization',
            name='shift_management_settings',
            field=models.JSONField(blank=True, default=organization.models.default_shift_management_settings),
        ),
    ]
