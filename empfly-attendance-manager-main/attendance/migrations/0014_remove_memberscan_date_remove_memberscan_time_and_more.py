# Generated by Django 4.0.2 on 2022-10-01 09:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0013_merge_20220930_1726'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='memberscan',
            name='date',
        ),
        migrations.RemoveField(
            model_name='memberscan',
            name='time',
        ),
        migrations.AddField(
            model_name='memberscan',
            name='date_time',
            field=models.DateTimeField(default='2022-10-01 09:55:27.696690'),
        ),
    ]
