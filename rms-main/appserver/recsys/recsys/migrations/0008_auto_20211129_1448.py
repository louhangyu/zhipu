# Generated by Django 3.2.5 on 2021-11-29 06:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recsys', '0007_auto_20211105_1018'),
    ]

    operations = [
        migrations.AddField(
            model_name='actionlog',
            name='device',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='actionlog',
            name='first_reach',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]