# Generated by Django 4.0.2 on 2022-10-05 13:22

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('member', '0025_remove_member_previous_roster_remove_member_rosters_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='profile',
            name='city',
        ),
    ]
