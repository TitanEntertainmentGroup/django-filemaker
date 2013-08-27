# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import hashlib
import mimetypes
import re
from decimal import Decimal

import requests
import urlobject
from dateutil import parser
from django.conf import settings
from django.core import validators
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.defaultfilters import slugify
from django.utils import timezone
from django.utils.encoding import (smart_text, smart_bytes, force_text,
                                   python_2_unicode_compatible)
from django.utils.six import string_types, text_type

from .exceptions import FileMakerValidationError
from .validators import validate_gtin

try:  # pragma: no cover
    from functools import total_ordering
except ImportError:  # pragma: no cover
    # Python < 2.7
    def total_ordering(cls):  # NOQA
        'Class decorator that fills-in missing ordering methods'
        convert = {
            '__lt__': [('__gt__', lambda self, other: other < self),
                       ('__le__', lambda self, other: not other < self),
                       ('__ge__', lambda self, other: not self < other)],
            '__le__': [('__ge__', lambda self, other: other <= self),
                       ('__lt__', lambda self, other: not other <= self),
                       ('__gt__', lambda self, other: not self <= other)],
            '__gt__': [('__lt__', lambda self, other: other > self),
                       ('__ge__', lambda self, other: not other > self),
                       ('__le__', lambda self, other: not self > other)],
            '__ge__': [('__le__', lambda self, other: other >= self),
                       ('__gt__', lambda self, other: not other >= self),
                       ('__lt__', lambda self, other: not self >= other)]
        }
        if hasattr(object, '__lt__'):
            roots = [op for op in convert
                     if getattr(cls, op) is not getattr(object, op)]
        else:
            roots = set(dir(cls)) & set(convert)
        assert roots, 'must define at least one ordering operation: < > <= >='
        root = max(roots)       # prefer __lt __ to __le__ to __gt__ to __ge__
        for opname, opfunc in convert[root]:
            if opname not in roots:
                opfunc.__name__ = opname
                opfunc.__doc__ = getattr(int, opname).__doc__
                setattr(cls, opname, opfunc)
        return cls

try:
    from pytz import NonExistentTimeError
except ImportError:
    class NonExistentTimeError(Exception):  # NOQA
        pass


@total_ordering
@python_2_unicode_compatible
class BaseFileMakerField(object):
    '''
    The base class that all FileMaker fields should inherit from.

    Sub-classes should generally override the coerce method which takes a
    value and should return it in the appropriate format.
    '''

    _value = None
    name = None
    fm_attr = None
    validators = []
    min = None
    max = None
    null_values = [None, '']
    fm_null_value = ''

    def __init__(self, fm_attr=None, *args, **kwargs):
        self.fm_attr = fm_attr
        self.null = kwargs.pop('null', False)
        self.default = kwargs.pop('default', None)
        self._value = self.default
        self.min = kwargs.pop('min', self.min)
        self.max = kwargs.pop('max', self.max)
        for key, value in kwargs.items():
            if key == 'fm_attr':
                continue
            setattr(self, key, value)

    def __str__(self):
        return smart_text(self.value)

    def __repr__(self):
        return '<{0}: {1}>'.format(self.__class__.__name__, smart_text(self))

    def __eq__(self, other):
        return self.value == other.value

    def __lt__(self, other):
        return self.value < other.value

    def __hash__(self):
        return '{0}{1}'.format(repr(self), self.name).__hash__()

    def _set_value(self, value):
        try:
            self._value = self._coerce(value)
        except (ValueError, TypeError, UnicodeError):
            raise FileMakerValidationError(
                '"{0}" is an invalid value for {1} ({2})'
                .format(value, self.name, self.__class__.__name__),
                field=self
            )

    def _get_value(self):
        return self._value

    value = property(_get_value, _set_value)

    def _coerce(self, value):
        if value in self.null_values:
            value = None
        if not self.null and self.default is not None and value is None:
            return self.default
        if self.null and value is None:
            return None
        elif value is None:
            raise ValueError('{0} cannot be None'.format(self.name))
        value = self.coerce(value)
        if self.min is not None and value < self.min:
            raise ValueError('{0} must be greater than or equal to {1}.'
                             .format(self.name, smart_text(self.min)))
        if self.max is not None and value > self.max:
            raise ValueError('{0} must be less than or equal to {1}.'
                             .format(self.name, smart_text(self.max)))
        if self.validators:
            for validator in self.validators:
                try:
                    validator(value)
                except ValidationError:
                    raise FileMakerValidationError(
                        '"{0}" is an invalid value for {1} ({2})'
                        .format(value, self.name, self.__class__.__name__),
                        field=self
                    )
        return value

    def coerce(self, value):
        raise NotImplementedError()

    def to_django(self, *args, **kwargs):
        return self.value

    def to_filemaker(self):
        return smart_text(self.value) if self.value \
            is not None else self.fm_null_value


class UnicodeField(BaseFileMakerField):
    '''
    Coerces data into a ``unicode`` object on Python 2.x or a ``str`` object on
    Python 3.x
    '''

    def coerce(self, value):
        return smart_text(value)


class CharField(UnicodeField):
    '''
    An alias for :py:class:`UnicodeField`.
    '''
    pass


class TextField(UnicodeField):
    '''
    An alias for :py:class:`UnicodeField`.
    '''
    pass


class BytesField(BaseFileMakerField):
    '''
    Coerces data into a bytestring instance
    '''

    def coerce(self, value):
        return smart_bytes(value)


class EmailField(CharField):
    '''
    A :py:class:`CharField` that vaidates that it's input is a valid email
    address.
    '''

    validators = [validators.validate_email]


class IPAddressField(CharField):
    '''
    A :py:class:`CharField` that validates that it's input is a valid IPv4
    or IPv6 address.
    '''

    validators = [validators.validate_ipv46_address]


class IPv4AddressField(CharField):
    '''
    A :py:class:`CharField` that validates that it's input is a valid IPv4
    address.
    '''

    validators = [validators.validate_ipv4_address]


class IPv6AddressField(CharField):
    '''
    A :py:class:`CharField` that validates that it's input is a valid IPv6
    address.
    '''

    validators = [validators.validate_ipv6_address]


class IntegerField(BaseFileMakerField):
    '''
    Coerces data into an integer.
    '''

    def coerce(self, value):
        return int(value)


class PositiveIntegerField(IntegerField):
    '''
    An :py:class:`IntegerField` that ensures it's input is 0 or greater.
    '''

    min = 0


class CommaSeparatedIntegerField(CharField):
    '''
    A :py:class:`CharField` that validates a comma separated list of integers
    '''

    validators = [validators.validate_comma_separated_integer_list]


class CommaSeparratedIntegerField(CommaSeparatedIntegerField):
    '''
    Alternate (misspelled) name for :py:class:`CommaSeparatedIntegerField`

    .. deprecated:: 0.1.1
        This field class is deprecated as of 0.1.1 and will disappear in 0.2.0.
        Use :py:class:`CommaSeparatedIntegerField` instead.
    '''

    def __init__(self, *args, **kwargs):
        import warnings
        warnings.warn(
            message='CommaSeparratedIntegerField is deprecated. Use '
                    'CommaSeparatedIntegerField.',
            category=DeprecationWarning,
        )
        super(CommaSeparatedIntegerField, self).__init__(*args, **kwargs)


class FloatField(BaseFileMakerField):
    '''
    Coerces data into a float.
    '''

    def coerce(self, value):
        return float(value)


class DecimalField(BaseFileMakerField):
    '''
    Coerces data into a decimal.Decimal object.

    :param decimal_places: (*Optional*) The number of decimal places to
        truncate input to.
    '''

    decimal_places = None

    def coerce(self, value):
        if not isinstance(value, Decimal):
            value = Decimal(smart_text(value))
        if self.decimal_places is not None \
                and isinstance(self.decimal_places, int):
            quant = '0'.join('' for x in range(self.decimal_places + 1))
            quant = Decimal('.{0}'.format(quant))
            value = value.quantize(quant)
        return value


@python_2_unicode_compatible
class DateTimeField(BaseFileMakerField):
    '''
    Coerces data into a datetime.datetime instance.

    :param strptime: An optional strptime string to use if falling back to the
        datetime.datetime.strptime method
    '''

    combine_datetime = datetime.time.min
    strptime = None

    def __str__(self):
        if self.value:
            return smart_text(self.value.isoformat())
        return 'None'

    def coerce(self, value):
        combined = False
        if isinstance(value, datetime.datetime):
            value = value
        elif isinstance(value, datetime.date):
            combined = True
            value = datetime.datetime.combine(value, self.combine_datetime)
        elif isinstance(value, string_types) and self.strptime is not None:
            value = datetime.datetime.strptime(value, self.strptime)
        elif isinstance(value, string_types) and value.strip():
            try:
                value = parser.parse(value)
            except OverflowError as e:
                try:
                    value = datetime.datetime.strptime(value, '%Y%m%d%H%M%S')
                except ValueError:
                    raise e
        elif isinstance(value, (list, tuple)):
            value = datetime.datetime(*value)
        elif isinstance(value, (int, float)):
            value = datetime.datetime.fromtimestamp(value)
        else:
            raise TypeError('Cannot convert {0} to datetime instance'
                            .format(type(value)))
        if settings.USE_TZ and timezone.is_naive(value):
            try:
                tz = timezone.get_current_timezone()
                if combined:
                    # If we combined the date with datetime.time.min we
                    # should adjust by dst to get the correct datetime
                    value += tz.dst(value)
                value = timezone.make_aware(
                    value, timezone.get_current_timezone())
            except NonExistentTimeError:
                value = timezone.get_current_timezone().localize(value)
            value = timezone.utc.normalize(value)
        elif not settings.USE_TZ and timezone.is_aware(value):
            value = timezone.make_naive(value, timezone.get_current_timezone())
        return value

    def to_filemaker(self):
        return getattr(self.value, 'isoformat', lambda: '')()


class DateField(DateTimeField):
    '''
    Coerces data into a datetime.date instance.

    :param strptime: An optional strptime string to use if falling back to the
        datetime.datetime.strptime method
    '''

    def coerce(self, value):
        dt = super(DateField, self).coerce(value)
        if timezone.is_aware(dt):
            dt = timezone.get_current_timezone().normalize(dt)
        return dt.date()


class BooleanField(BaseFileMakerField):
    '''
    Coerces data into a boolean.

    :param map: An optional dictionary mapping that maps values to their
        Boolean counterparts.
    '''

    def __init__(self, fm_attr=None, *args, **kwargs):
        self.map = kwargs.pop('map', {})
        self.reverse_map = dict((v, k) for k, v in self.map.items())
        return super(BooleanField, self).__init__(
            fm_attr=fm_attr, *args, **kwargs)

    def coerce(self, value):
        if value in list(self.map.keys()):
            return self.map.get(value)
        if isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            return not value == 0
        elif isinstance(value, string_types):
            value = value.strip().lower()
            if value in ['y', 'yes', 'true', 't', '1']:
                return True
            return False
        else:
            return bool(value)

    def to_filemaker(self):
        if self.value in self.reverse_map:
            return self.reverse_map.get(self.value)
        return force_text(self.value).lower() if self.value \
            is not None else self.fm_null_value


class NullBooleanField(BooleanField):
    '''
    A BooleanField that also accepts a null value
    '''

    null = True

    def coerce(self, value):
        if value is None:
            return None
        if value in ('None',):
            return None
        return super(NullBooleanField, self).coerce(value)


class ListField(BaseFileMakerField):
    '''
    A field that takes a list of values of other types.

    :param base_type: The base field type to use.
    '''

    base_type = None

    def __init__(self, fm_attr=None, *args, **kwargs):
        self.base_type = kwargs.pop('base_type', None)
        if self.base_type is None:
            raise ValueError('You must specify a base_type')
        return super(ListField, self)\
            .__init__(fm_attr=fm_attr, *args, **kwargs)

    def coerce(self, value):
        values = []
        for val in value:
            sub_type = self.base_type()
            sub_type.value = val
            values.append(sub_type.value)
        return values

    def to_django(self, *args, **kwargs):
        try:
            return [v.to_django(*args, **kwargs) for v in self.value]
        except AttributeError:
            return self.value

    def to_filemaker(self):
        values = []
        for val in self.value:
            sub_type = self.base_type()
            sub_type.value = val
            values.append(sub_type.to_filemaker())
        return values


class ModelField(BaseFileMakerField):
    '''
    A field that provides a refernce to an instance of another filemaker model,
    equivalent to a Django ForeignKey.

    :param model: The FileMaker model to reference.
    '''

    model = None

    def __init__(self, fm_attr=None, *args, **kwargs):
        self.model = kwargs.pop('model', None)
        if self.model is None:
            raise ValueError('You must specify a model')
        return super(ModelField, self)\
            .__init__(fm_attr=fm_attr, *args, **kwargs)

    def coerce(self, value):
        try:
            return self.model(value)
        except FileMakerValidationError:
            if self.default:
                return self.default
            if self.null:
                return None
            raise

    def to_django(self, *args, **kwargs):
        if self.value:
            return self.value.to_django(*args, **kwargs)
        return None

    def to_filemaker(self):
        if self.value:
            return self.value.to_filemaker()
        return ''

    def contribute_to_class(self, cls):
        self.model._meta['related'].append((cls, self.name))


class ToOneField(ModelField):
    '''
    An alias for :py:class:`ModelField`
    '''
    pass


class ModelListField(BaseFileMakerField):
    '''
    A fields that gives a reference to a list of models, equivalent to a
    Django ManyToMany relation.

    :param model: The model class to reference.
    '''

    model = None

    def __init__(self, fm_attr=None, *args, **kwargs):
        self.model = kwargs.pop('model', None)
        if self.model is None:
            raise ValueError('You must specify a model')
        return super(ModelListField, self)\
            .__init__(fm_attr=fm_attr, *args, **kwargs)

    def coerce(self, value):
        instances = []
        for v in value:
            instances.append(self.model(v)
                             if not isinstance(v, self.model)
                             else v)
        return instances

    def to_django(self, *args, **kwargs):
        return [m.to_django(*args, **kwargs) for m in self.value]

    def to_filemaker(self):
        return [m.to_filemaker() for m in self.value]

    def contribute_to_class(self, cls):
        self.model._meta['many_related'].append((cls, self.name))


class ToManyField(ModelListField):
    '''
    An alias for :py:class:`ModelListField`.
    '''
    pass


@python_2_unicode_compatible
class PercentageField(DecimalField):
    '''
    A :py:class:`DecimalField` that ensures it's input is between 0 and 100
    '''

    min = Decimal('0')
    max = Decimal('100')

    def __str__(self):
        return '{0}%'.format(smart_text(self.value))


class CurrencyField(DecimalField):
    '''
    A decimal field that uses 2 decimal places and strips off any currency
    symbol from the start of it's input.

    Has a default minimum value of ``0.00``.
    '''

    min = Decimal('0.00')
    decimal_places = 2

    def coerce(self, value):
        if isinstance(value, string_types):
            symbols = [
                '¤', '؋', '฿', 'B/.', 'Bs.', 'Bs.F.', 'GH¢', '¢', 'Ch.', '₡',
                'D', 'ден', 'دج', '.د.ب', 'د.ع', 'د.ك', 'ل.د', 'дин', 'د.ت',
                'د.م.', 'د.إ', '\$', '[a-zA-z]{1,3}\$', '\$[a-zA-Z]{1,3}',
                '元', '圓', '元', '圓', '₫', '€', '€', 'ƒ', 'Afl.', 'NAƒ',
                'FCFA', '₣', 'G₣', 'S₣', 'Fr.', '₲', '₴', '₭', 'Kč', 'Íkr',
                'K.D.', 'ლ', 'm.', '₥', '₦', 'Nu.', '₱', '£', '₤',
                '[a-zA-Z]{1,2}[£₤]', 'ج.م.', 'Pt.', 'ريال', 'ر.ع.', 'ر.ق',
                'ر.س',  'ریال', '៛', '₹', '₹', '₨', '₪', 'KSh', 'Sh.So.',
                'S/.', 'лв', 'сом', '৳', '₸', '₮', 'VT', '₩', '¥', '円', '圓',
                '元', '圆', 'zł', '₳', '₢', '₰', '₯', '₠', 'ƒ', '₣', '₤',
                'Kčs', 'ℳ', '₧', 'ℛℳ', '₷', '₶', '[a-zA-Z]{1,4}',
            ]
            value = re.sub(
                r'^({0})'.format(r'|'.join(symbols)), '', value.strip()
            ).strip()
        return super(CurrencyField, self).coerce(value)


class SlugField(CharField):
    '''
    A :py:class:`CharField` that validates it's input is a valid slug.
    Will automatically slugify it's input, by default.
    Can also be passed a specific slugify function.

    .. note::

        If the custom ``slugify`` function would create a slug that would fail
        a test by  ``django.core.validators.validate_slug`` it may be wise to
        pass in a different or empty ``validators`` list.

    :param auto: Whether to slugify input. Defaults to ``True``.
    :param slugify: The slugify function to use. Defaults to
        ``django.template.defaultfilters.slugify``.
    '''

    validators = [validators.validate_slug]

    def __init__(self, fm_attr=None, *args, **kwargs):
        self.slugify = kwargs.pop('slugify', slugify)
        self.auto = kwargs.pop('auto', True)
        return super(SlugField, self)\
            .__init__(fm_attr=fm_attr, *args, **kwargs)

    def coerce(self, value):
        value = super(SlugField, self).coerce(value)
        if self.auto:
            value = self.slugify(value)
        return value


class GTINField(CharField):
    '''
    A :py:class:`CharField` that validates it's input is a valid
    `GTIN <https://en.wikipedia.org/wiki/Global_Trade_Item_Number>`_.
    '''

    validators = [validate_gtin]


class URLField(CharField):
    '''
    A :py:class:`CharField` that validates it's input is a valid URL.
    '''

    validators = [validators.URLValidator()]


class FileField(BaseFileMakerField):
    '''
    A field that downloads file data (e.g. from the FileMaker web interface).
    The file will be saved with a filename that is the combination of the
    hash of it's contents, and the extension associated with the mimetype it
    was served with.

    Can be given an optional ``base_url`` with which the URL received from
    FileMaker will be joined.

    :param retries: The number of retries to make when downloading the file in
        case of errors. Defaults to ``5``.
    :param base_url: The URL with which to combine the url received from
        FileMaker, empty by default.
    :param storage: The Django storage class to use when saving the file.
        Defaults to the default storage class.
    '''

    retries = 5
    base_url = ''
    storage = default_storage

    def __init__(self, fm_attr=None, *args, **kwargs):
        self.base_url = urlobject.URLObject(kwargs.pop('base_url', ''))
        return super(FileField, self)\
            .__init__(fm_attr=fm_attr, *args, **kwargs)

    def _get_http(self, url):
        try:
            r = requests.get(url.without_auth(), auth=url.auth)
            r.raise_for_status()
            return r.content, \
                r.headers.get('Content-Type', '').split(';')[0]
        except requests.RequestException:
            return None, None

    def _get_file(self, url):
        content, mime = None, None
        for i in range(self.retries):
            if url.scheme in ('http', 'https'):
                get = self._get_http
            else:
                raise FileMakerValidationError(
                    'Unable to obtain file via "{0}"'.format(url.scheme))
            content, mime = get(url)
            if content is not None and mime is not None:
                break
        if content is None or mime is None:
            raise FileMakerValidationError(
                'Could not get file from: {0}'.format(url))
        if mime in ('image/jpeg', 'image/jpe', 'image/jpg'):
            mime = 'image/jpg'
        fname = '{0}{1}'.format(
            hashlib.md5(smart_bytes(content)).hexdigest()[:20],
            mimetypes.guess_extension(mime, strict=False),
        )
        return {'filename': fname, 'content': content, 'content-type': mime}

    def coerce(self, value):
        url = urlobject.URLObject(smart_text(value or ''))
        try:
            if not url.scheme:
                url = url.with_scheme(self.base_url.scheme or '')
            if not url.hostname:
                url = url.with_hostname(self.base_url.hostname or '')
            if url.auth == (None, None) \
                    and not self.base_url.auth == (None, None):
                url = url.with_auth(*self.base_url.auth)
        except (TypeError, ValueError):  # pragma: no cover
            raise FileMakerValidationError('Could not determine file url.')
        return self._get_file(url)

    def to_django(self, *args, **kwargs):
        return SimpleUploadedFile.from_dict(self.value) if self.value else None

    def to_filemaker(self):
        return self.storage.url(self.value['filename']) \
            if self.value is not None and self.value.get('filename', None) \
            else self.fm_null_value


class ImageField(FileField):
    '''
    A :py:class:`FileField` that expects the mimetype of the received file to
    be ``image/*``.
    '''

    def _get_file(self, url):
        f = super(ImageField, self)._get_file(url)
        if not f.content_type.split('/')[0] == 'image':
            raise FileMakerValidationError(
                '"{0}" is not a valid image type.'.format(f.content_type))
        return f


class UploadedFileField(BaseFileMakerField):
    '''
    Takes the path of a file that has already been uploaded to storage and
    generates a File instance from it.

    :param storage: An instance of the storage class to use
    '''

    storage = default_storage

    def coerce(self, value):
        value = re.sub(
            r'^[\s\/\.]+', '', text_type(urlobject.URLObject(value).path))
        try:
            f = self.storage.open(value)
        except (Exception, EnvironmentError):
            raise FileMakerValidationError(
                'Could not open file "{0}".'.format(value))
        else:
            return {'file': f, 'filename': f.name}

    def to_django(self, *args, **kwargs):
        return self.value['file'] if self.value else None

    def to_filemaker(self):
        return self.storage.url(self.value['filename']) \
            if self.value else self.fm_null_value
