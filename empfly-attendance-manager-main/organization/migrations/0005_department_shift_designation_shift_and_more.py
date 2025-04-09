# Generated by Django 4.0.2 on 2022-08-18 12:52

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shift', '0001_initial'),
        ('organization', '0004_alter_systemlocation_radius_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='department',
            name='shift',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='departments', to='shift.shift'),
        ),
        migrations.AddField(
            model_name='designation',
            name='shift',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='designations', to='shift.shift'),
        ),
        migrations.AddField(
            model_name='organizationlocation',
            name='shift',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='organization_locations', to='shift.shift'),
        ),
    ]
