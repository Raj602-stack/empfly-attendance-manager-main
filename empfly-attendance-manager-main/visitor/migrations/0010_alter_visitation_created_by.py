# Generated by Django 4.0.2 on 2022-08-06 09:32

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('visitor', '0009_alter_visitation_org_location_alter_visitation_scans'),
    ]

    operations = [
        migrations.AlterField(
            model_name='visitation',
            name='created_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visitation', to=settings.AUTH_USER_MODEL),
        ),
    ]
