# Generated by Django 4.0.2 on 2022-08-10 06:07

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0002_alter_user_groups_alter_user_user_permissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='OTP',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('email', models.EmailField(max_length=254)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
