# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.validators import RegexValidator


gtin_re = r'^[0-9]{6,8}$|^[0-9]{10}$|^[0-9]{12}$|^[0-9]{13}$|^[0-9]{14,}$'

validate_gtin = \
    RegexValidator(gtin_re, 'Please enter a valid GTIN/ISBN/EAN/UPC code.')
