# Generated by Django 4.0.2 on 2022-08-06 07:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0004_alter_systemlocation_radius_and_more'),
        ('visitor', '0007_alter_visitation_scans'),
    ]

    operations = [
        migrations.AddField(
            model_name='visitation',
            name='host_status',
            field=models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='pending', max_length=50),
        ),
        migrations.AddField(
            model_name='visitation',
            name='org_location',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='visitation', to='organization.organizationlocation'),
        ),
        migrations.AddField(
            model_name='visitation',
            name='visitation_status',
            field=models.CharField(choices=[('created', 'Created'), ('scheduled', 'Scheduled'), ('cancelled', 'Cancelled'), ('completed', 'Completed')], default='pending', max_length=50),
        ),
        migrations.AddField(
            model_name='visitation',
            name='visitor_status',
            field=models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='pending', max_length=50),
        ),
    ]
