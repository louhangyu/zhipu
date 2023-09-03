# Generated by Django 3.2.5 on 2022-05-13 03:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recsys', '0022_hotpaper_report_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='hotpaper',
            name='report_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='hotpaper',
            name='report_from',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='hotpaper',
            name='report_title',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]