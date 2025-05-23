# Generated by Django 4.0.2 on 2022-10-21 09:17

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('member', '0028_remove_profile_government_id_type_and_more'),
        ('organization', '0020_systemlocation_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='department',
            name='department_head',
            field=models.OneToOneField(default=1, on_delete=django.db.models.deletion.RESTRICT, related_name='department_head', to='member.member'),
            preserve_default=False,
        ),
    ]
