# Generated by Django 4.0.2 on 2024-08-20 09:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0033_designation_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='designation',
            name='status',
        ),
    ]
