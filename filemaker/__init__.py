# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from distutils import version


__version__ = '0.2.0'
version_info = version.StrictVersion(__version__).version


from .base import FileMakerModel  # NOQA
from .exceptions import *  # NOQA
from . import fields  # NOQA
