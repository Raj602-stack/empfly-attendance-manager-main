# Generated by Django 4.0.2 on 2022-10-12 18:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0019_organization_kiosk_management_settings'),
        ('kiosk', '0008_alter_kiosk_org_location'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='kiosk',
            unique_together={('kiosk_name', 'organization')},
        ),
    ]
