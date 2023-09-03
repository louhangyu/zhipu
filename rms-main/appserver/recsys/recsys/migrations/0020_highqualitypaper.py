# Generated by Django 3.2.5 on 2022-05-10 02:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recsys', '0019_actionlog_recall_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='HighQualityPaper',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('paper_id', models.CharField(max_length=24, unique=True)),
                ('title', models.CharField(max_length=255)),
                ('tags', models.CharField(blank=True, max_length=255, null=True)),
                ('abstract', models.TextField()),
                ('authors', models.CharField(blank=True, max_length=255, null=True)),
                ('venue', models.CharField(max_length=255)),
                ('affiliations', models.TextField(blank=True, null=True)),
                ('ts', models.DateTimeField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
