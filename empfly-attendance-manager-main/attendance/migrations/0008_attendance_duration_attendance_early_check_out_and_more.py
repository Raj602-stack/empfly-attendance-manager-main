# Generated by Django 4.0.4 on 2022-09-27 11:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0007_remove_attendance_duration_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='duration',
            field=models.FloatField(blank=True, default=0.0, null=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='early_check_out',
            field=models.FloatField(blank=True, default=0.0, null=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='late_check_in',
            field=models.FloatField(blank=True, default=0.0, null=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='overtime',
            field=models.FloatField(blank=True, default=0.0, null=True),
        ),
    ]
