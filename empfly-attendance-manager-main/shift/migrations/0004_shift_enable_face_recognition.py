# Generated by Django 4.0.2 on 2022-09-03 11:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shift', '0003_alter_shift_unique_together'),
    ]

    operations = [
        migrations.AddField(
            model_name='shift',
            name='enable_face_recognition',
            field=models.BooleanField(default=True),
        ),
    ]
