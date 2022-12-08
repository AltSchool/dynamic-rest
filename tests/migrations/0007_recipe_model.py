# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.contrib.postgres.fields import JSONField


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0006_auto_20210921_1026'),
    ]

    operations = [
        migrations.CreateModel(
            name='recipe',
            fields=[
                ('name', models.CharField(max_length=60)),
                ('ingredients', JSONField(null=True))
            ]
        ),
    ]
