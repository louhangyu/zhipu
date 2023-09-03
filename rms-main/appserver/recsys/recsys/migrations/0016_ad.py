# Generated by Django 3.2.5 on 2022-04-14 08:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recsys', '0015_coldkeyword'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.TextField()),
                ('title_zh', models.TextField()),
                ('keywords', models.TextField()),
                ('url', models.URLField(max_length=4096)),
                ('author_ids', models.TextField()),
                ('total', models.IntegerField()),
                ('desc', models.TextField()),
                ('desc_zh', models.TextField()),
                ('create_at', models.DateTimeField(auto_now_add=True)),
                ('modify_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]