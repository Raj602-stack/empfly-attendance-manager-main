# Generated by Django 4.0.2 on 2023-01-30 12:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0027_attendancecomputationhistory_attendance_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attendancecomputationhistory',
            name='attendance_date',
            field=models.DateField(),
        ),
    ]
