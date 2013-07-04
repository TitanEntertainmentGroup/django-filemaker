# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.utils.importlib import import_module
from django.utils.six import string_types

from .conf import settings


def import_string(s):
    mod, attr = s.rsplit('.', 1)
    return getattr(import_module(mod), attr)


def get_field_class(cls):
    '''
    Returns the FileMaker class that matches the given django field class
    '''
    if isinstance(cls, string_types):
        cls = import_string(cls)
    elif not isinstance(cls, type):
        cls = type(cls)
    fm_cls = settings.FILEMAKER_DJANGO_FIELD_MAP.get(cls, None)
    if isinstance(fm_cls, string_types):
        fm_cls = import_string(fm_cls)
    return fm_cls
