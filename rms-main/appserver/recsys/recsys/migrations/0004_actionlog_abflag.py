# Generated by Django 3.2.5 on 2021-08-30 02:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recsys', '0003_alter_actionlog_create_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='actionlog',
            name='abflag',
            field=models.CharField(blank=True, max_length=12, null=True),
        ),
    ]