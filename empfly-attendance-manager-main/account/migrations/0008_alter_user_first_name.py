# Generated by Django 4.0.4 on 2022-10-04 15:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0007_alter_user_phone'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='first_name',
            field=models.CharField(default='', max_length=200),
            preserve_default=False,
        ),
    ]
