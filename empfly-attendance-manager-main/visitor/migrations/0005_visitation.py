# Generated by Django 4.0.2 on 2022-08-06 06:15

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('member', '0016_remove_profile_theme'),
        ('kiosk', '0003_initial'),
        ('visitor', '0004_visitorscan'),
    ]

    operations = [
        migrations.CreateModel(
            name='Visitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(max_length=200)),
                ('visitation_date', models.DateField(auto_now_add=True)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('allowed_kiosks', models.ManyToManyField(related_name='kiosks', to='kiosk.Kiosk')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visitation', to='member.member')),
                ('host', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visitation_host', to='member.member')),
                ('visitor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visitation', to='visitor.visitor')),
            ],
        ),
    ]
