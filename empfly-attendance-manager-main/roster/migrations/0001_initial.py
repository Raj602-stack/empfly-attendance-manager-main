# Generated by Django 4.0.4 on 2022-06-16 08:16

from django.db import migrations, models
import django.db.models.deletion
import roster.models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('organization', '0001_initial'),
        ('member', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Location',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True)),
                ('latitude', models.DecimalField(decimal_places=14, max_digits=18)),
                ('longitude', models.DecimalField(decimal_places=14, max_digits=18)),
                ('radius', models.FloatField(default=50.0)),
                ('email', models.CharField(blank=True, max_length=320, null=True)),
                ('phone', models.CharField(blank=True, max_length=20, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='location_created_by', to='member.member')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='locations', to='organization.organization')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='location_updated_by', to='member.member')),
            ],
        ),
        migrations.CreateModel(
            name='Shift',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('duration', models.DurationField()),
                ('computation_time', models.TimeField()),
                ('overtime', models.DurationField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('settings', models.JSONField(blank=True, default=roster.models.default_shift_config, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='shift_created_by', to='member.member')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shifts', to='organization.organization')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='shift_updated_by', to='member.member')),
            ],
            options={
                'unique_together': {('organization', 'name')},
            },
        ),
        migrations.CreateModel(
            name='Cluster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True)),
                ('locations', models.ManyToManyField(blank=True, related_name='cluster', to='roster.location')),
                ('managers', models.ManyToManyField(related_name='clusters', to='member.member')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clusters', to='organization.organization')),
            ],
        ),
        migrations.CreateModel(
            name='Roster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='roster_created_by', to='member.member')),
                ('location', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rosters', to='roster.location')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rosters', to='organization.organization')),
                ('shift', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rosters', to='roster.shift')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='roster_updated_by', to='member.member')),
            ],
            options={
                'unique_together': {('organization', 'name')},
            },
        ),
        migrations.AddConstraint(
            model_name='location',
            constraint=models.CheckConstraint(check=models.Q(('radius__gte', 0.0), ('radius__lte', 5000.0)), name='location_radius_range'),
        ),
        migrations.AlterUniqueTogether(
            name='location',
            unique_together={('organization', 'name')},
        ),
        migrations.AlterUniqueTogether(
            name='cluster',
            unique_together={('organization', 'name')},
        ),
    ]
