# Generated by Django 4.0.2 on 2022-08-18 13:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shift', '0001_initial'),
        ('member', '0018_member_shift'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='applicable_shift',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='applicable_members', to='shift.shift'),
        ),
    ]
