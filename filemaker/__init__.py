# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from distutils import version


__version__ = '0.2.2'
version_info = version.StrictVersion(__version__).version


from filemaker.base import FileMakerModel  # NOQA
from filemaker.exceptions import *  # NOQA
from filemaker import fields  # NOQA
