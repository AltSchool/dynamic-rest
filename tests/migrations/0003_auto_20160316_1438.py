# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('tests', '0002_cat_is_dead'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='favorite_pet_id',
            field=models.TextField(null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='user',
            name='favorite_pet_type',
            field=models.ForeignKey(blank=True, to='contenttypes.ContentType', null=True),  # noqa
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='group',
            name='name',
            field=models.TextField(unique=True),
            preserve_default=True,
        ),
    ]
