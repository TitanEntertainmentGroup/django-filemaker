# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from appconf import AppConf
from django.conf import settings  # NOQA
from django.utils.importlib import import_module
from django.utils.six import string_types


class FilemakerAppConf(AppConf):

    from django.db.models import fields

    DJANGO_FIELD_MAP = {
        fields.BooleanField: 'filemaker.fields.BooleanField',
        fields.CharField: 'filemaker.fields.CharField',
        fields.CommaSeparatedIntegerField:
        'filemaker.fields.CommaSeparatedIntegerField',
        fields.DateField: 'filemaker.fields.DateField',
        fields.DateTimeField: 'filemaker.fields.DateTimeField',
        fields.DecimalField: 'filemaker.fields.DecimalField',
        fields.EmailField: 'filemaker.fields.EmailField',
        fields.FilePathField: 'filemaker.fields.CharField',
        fields.FloatField: 'filemaker.fields.FloatField',
        fields.IntegerField: 'filemaker.fields.IntegerField',
        fields.BigIntegerField: 'filemaker.fields.IntegerField',
        fields.IPAddressField: 'filemaker.fields.IPAddressField',
        fields.GenericIPAddressField: 'filemaker.fields.IPAddressField',
        fields.NullBooleanField: 'filemaker.fields.NullBooleanField',
        fields.PositiveIntegerField: 'filemaker.fields.PositiveIntegerField',
        fields.PositiveSmallIntegerField:
        'filemaker.fields.PositiveIntegerField',
        fields.SlugField: 'filemaker.fields.SlugField',
        fields.SmallIntegerField: 'filemaker.fields.IntegerField',
        fields.TextField: 'filemaker.fields.TextField',
        fields.TimeField: 'filemaker.fields.DateTimeField',
        fields.URLField: 'filemaker.fields.URLField',
    }
    DJANGO_FIELD_MAP_OVERRIDES = {}

    class Meta:
        prefix = 'filemaker'

    def _import(self, s):  # pragma: no cover
        mod, attr = s.rsplit('.', 1)
        return getattr(import_module(mod), attr)

    def configure(self):
        overrides = self.configured_data.get('DJANGO_FIELD_MAP_OVERRIDES')
        for k, v in overrides:  # pragma: no cover
            if isinstance(k, string_types):
                overrides[self._import(k)] = v
                del overrides[k]
        self.configured_data['DJANGO_FIELD_MAP'].update(overrides)
        return self.configured_data
