# Generated by Django 3.2.5 on 2022-09-19 09:51

from django.db import migrations, models
import recsys.models


class Migration(migrations.Migration):

    dependencies = [
        ('recsys', '0027_highqualitypaper_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='highqualitypaper',
            name='year',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='highqualitypaper',
            name='paper_id',
            field=models.CharField(max_length=24, unique=True, validators=[recsys.models.validate_paper_id]),
        ),
    ]
