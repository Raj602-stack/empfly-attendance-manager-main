# Generated by Django 4.0.2 on 2022-10-29 06:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0022_alter_memberscan_scan_type'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='attendancecomputationhistory',
            options={'ordering': ['-updated_at']},
        ),
    ]
