# Generated by Django 4.0.2 on 2022-09-30 17:21

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0011_memberscan_organization'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='attendance',
            name='roster',
        ),
    ]
