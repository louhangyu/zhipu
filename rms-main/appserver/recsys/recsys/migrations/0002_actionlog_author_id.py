# Generated by Django 3.2.5 on 2021-08-27 06:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recsys', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='actionlog',
            name='author_id',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
