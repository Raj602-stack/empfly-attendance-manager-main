# Generated by Django 4.0.2 on 2022-09-27 09:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0007_remove_memberscan_datetime_memberscan_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='memberscan',
            name='date',
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name='memberscan',
            name='time',
            field=models.TimeField(),
        ),
    ]
