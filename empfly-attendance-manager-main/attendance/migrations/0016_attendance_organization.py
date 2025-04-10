# Generated by Django 4.0.4 on 2022-10-03 06:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0014_holiday_org_location'),
        ('attendance', '0015_alter_memberscan_date_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='organization',
            field=models.ForeignKey(default='', on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='organization.organization'),
            preserve_default=False,
        ),
    ]
