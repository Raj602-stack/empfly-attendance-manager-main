# Generated by Django 4.0.2 on 2022-08-16 16:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('visitor', '0019_alter_visitorscan_kiosk_alter_visitorscan_visitation_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='VisitorImage',
        ),
    ]
