# Generated by Django 4.0.2 on 2022-08-03 05:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('member', '0014_remove_profile_title_profile_pin_code_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='marital_status',
            field=models.CharField(blank=True, choices=[('single', 'Single'), ('married', 'Married')], max_length=200, null=True),
        ),
    ]
