# Generated by Django 4.0.2 on 2022-08-12 07:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('kiosk', '0004_alter_kiosk_end_time_alter_kiosk_start_time'),
        ('visitor', '0018_alter_visitorscan_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='visitorscan',
            name='kiosk',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visitor_scan', to='kiosk.kiosk'),
        ),
        migrations.AlterField(
            model_name='visitorscan',
            name='visitation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visitor_scan', to='visitor.visitation'),
        ),
        migrations.AlterField(
            model_name='visitorscan',
            name='visitor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visitor_scan', to='visitor.visitor'),
        ),
    ]
