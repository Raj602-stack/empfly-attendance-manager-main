# Generated by Django 4.0.2 on 2022-09-10 09:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shift', '0004_shift_enable_face_recognition'),
        ('organization', '0009_alter_orglocation_organization_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='default_shift',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='shift.shift'),
        ),
    ]
