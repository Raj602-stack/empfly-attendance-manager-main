# Generated by Django 4.0.2 on 2022-09-30 09:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0013_alter_organization_default_shift'),
        ('visitor', '0024_alter_visitation_end_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='visitation',
            name='organization',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='visitation', to='organization.organization'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='visitorscan',
            name='organization',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='visitor_scan', to='organization.organization'),
            preserve_default=False,
        ),
    ]
