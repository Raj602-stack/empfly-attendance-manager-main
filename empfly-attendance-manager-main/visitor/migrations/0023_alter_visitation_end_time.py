# Generated by Django 4.0.2 on 2022-08-27 07:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('visitor', '0022_remove_visitor_authorized_kiosks_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='visitation',
            name='end_time',
            field=models.TimeField(null=True),
        ),
    ]
