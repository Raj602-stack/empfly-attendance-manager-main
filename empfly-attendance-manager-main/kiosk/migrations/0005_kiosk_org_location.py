# Generated by Django 4.0.2 on 2022-10-12 06:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0018_alter_state_unique_together_remove_state_country_and_more'),
        ('kiosk', '0004_alter_kiosk_end_time_alter_kiosk_start_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='kiosk',
            name='org_location',
            field=models.ManyToManyField(to='organization.Organization'),
        ),
    ]
