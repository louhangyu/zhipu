# Generated by Django 4.2 on 2023-05-30 05:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recsys', '0040_chatround_assistant_extend_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatround',
            name='extend_spend_seconds',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='chatround',
            name='spend_seconds',
            field=models.FloatField(default=0.0),
        ),
    ]
