# Generated by Django 4.0.4 on 2022-06-21 09:15

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('member', '0002_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='profile',
            old_name='user',
            new_name='member',
        ),
    ]
