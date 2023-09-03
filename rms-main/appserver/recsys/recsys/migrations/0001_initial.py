# Generated by Django 3.2.5 on 2021-08-27 06:10

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('create_at', models.DateTimeField(auto_created=True)),
                ('uid', models.CharField(blank=True, max_length=64, null=True)),
                ('ud', models.CharField(blank=True, max_length=64, null=True)),
                ('up', models.CharField(blank=True, max_length=64, null=True)),
                ('ip', models.CharField(blank=True, max_length=32, null=True)),
                ('pub_ids', models.CharField(blank=True, max_length=4096, null=True)),
                ('keywords', models.CharField(blank=True, max_length=4096, null=True)),
                ('action', models.SmallIntegerField()),
            ],
        ),
    ]
