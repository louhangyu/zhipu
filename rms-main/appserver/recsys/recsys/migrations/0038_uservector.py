# Generated by Django 3.2.5 on 2023-04-10 07:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recsys', '0037_chineseenglish'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserVector',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uid', models.CharField(max_length=128, unique=True)),
                ('subscribes', models.JSONField(blank=True, null=True)),
                ('gender', models.IntegerField(blank=True, null=True)),
                ('title', models.CharField(blank=True, max_length=255, null=True)),
                ('vector', models.JSONField(blank=True, null=True)),
                ('cluster', models.IntegerField(blank=True, null=True)),
                ('update_at', models.DateTimeField(auto_now=True)),
                ('create_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
