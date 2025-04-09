# Generated by Django 4.0.2 on 2022-07-29 12:28

from django.db import migrations, models
import member.models


class Migration(migrations.Migration):

    dependencies = [
        ('member', '0010_profile_photo'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='profile',
            name='photo',
        ),
        migrations.AddField(
            model_name='member',
            name='photo',
            field=models.ImageField(blank=True, null=True, upload_to=member.models.rename_profile_image),
        ),
    ]
