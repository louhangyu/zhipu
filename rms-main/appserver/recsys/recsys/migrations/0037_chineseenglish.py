# Generated by Django 3.2.5 on 2023-03-29 01:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recsys', '0036_auto_20230206_1414'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChineseEnglish',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ch', models.CharField(blank=True, max_length=255, null=True)),
                ('eng', models.CharField(blank=True, max_length=255, null=True)),
                ('translator', models.CharField(max_length=64)),
                ('create_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'unique_together': {('ch', 'eng')},
            },
        ),
    ]
