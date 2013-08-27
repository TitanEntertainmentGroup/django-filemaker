# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import itertools
import time
from decimal import Decimal

import urlobject
from django.contrib.redirects.models import Redirect
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db.models.fields import CharField, IntegerField
from django.http import QueryDict
from django.test import TransactionTestCase
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.six import text_type
from httpretty import httprettified, HTTPretty
from mock import Mock, NonCallableMock, NonCallableMagicMock, patch, MagicMock

from filemaker import fields, FileMakerValidationError, FileMakerModel
from filemaker.base import deep_getattr
from filemaker.manager import RawManager, Manager
from filemaker.utils import get_field_class


class TestFilemakerFields(TransactionTestCase):

    def test_default_and_null(self):
        f = fields.IntegerField(null=True)
        f.value = None
        self.assertEqual(f.value, None)
        f.value = 3
        self.assertEqual(f.value, 3)
        f = fields.IntegerField(default=2)
        self.assertEqual(f.value, 2)
        f.value = None
        self.assertEqual(f.value, 2)
        f.value = 3
        self.assertEqual(f.value, 3)
        f = fields.IntegerField(default=2, null=True)
        self.assertEqual(f.value, 2)
        f.value = None
        self.assertEqual(f.value, None)
        f.value = 3
        self.assertEqual(f.value, 3)
        f = fields.IntegerField(null=False, default=None)
        with self.assertRaises(FileMakerValidationError):
            f.value = None

    def test_min_max(self):
        f = fields.IntegerField(min=2)
        with self.assertRaises(FileMakerValidationError):
            f.value = 1
        f.value = 3
        self.assertEqual(f.value, 3)
        f = fields.IntegerField(max=2)
        with self.assertRaises(FileMakerValidationError):
            f.value = 3
        f.value = 1
        self.assertEqual(f.value, 1)
        f = fields.IntegerField(min=2, max=3)
        with self.assertRaises(FileMakerValidationError):
            f.value = 1
        with self.assertRaises(FileMakerValidationError):
            f.value = 4
        f.value = 2
        self.assertEqual(f.value, 2)
        f.value = 3
        self.assertEqual(f.value, 3)

    def test_comparison(self):
        f1 = fields.IntegerField()
        f2 = fields.IntegerField()
        f1.value = 1
        f2.value = 1
        self.assertEqual(f1, f2)
        f2.value = 2
        self.assertGreater(f2, f1)
        self.assertLess(f1, f2)
        f2 = fields.DecimalField()
        f2.value = '1'
        self.assertEqual(f1, f2)

    def test_hash(self):
        f1 = fields.IntegerField()
        f2 = fields.IntegerField()
        self.assertEqual(hash(f1), hash(f2))
        f1.value = 1
        self.assertNotEqual(hash(f1), hash(f2))
        f2.value = 1
        self.assertEqual(hash(f1), hash(f2))
        f1.name = 'test'
        self.assertNotEqual(hash(f1), hash(f2))
        {f1: 123}

    def test_text_methods(self):
        f = fields.CharField()
        f.value = 'abc'
        self.assertEqual(text_type(f), 'abc')
        self.assertIn('abc', repr(f))
        f = fields.PercentageField()
        f.value = '20'
        self.assertEqual(text_type(f), '20%')
        self.assertIn('20%', repr(f))
        f = fields.DateTimeField()
        self.assertTrue(text_type(f))
        now = timezone.now()
        f.value = now
        self.assertEqual(text_type(f), now.isoformat())
        self.assertIn(now.isoformat(), repr(f))

    def test_to_django(self):
        f = fields.IntegerField(null=True)
        f.value = 3
        self.assertEqual(f.to_django(), 3)

    def test_unicode_field(self):
        f = fields.UnicodeField()
        f.value = 2
        self.assertEqual(f.value, '2')
        self.assertTrue(isinstance(f.value, text_type))
        f.value = b'abc'
        self.assertEqual(f.value, 'abc')
        self.assertTrue(isinstance(f.value, text_type))

    def test_unicode_synonyms(self):
        self.assertTrue(issubclass(fields.CharField, fields.UnicodeField))
        self.assertTrue(issubclass(fields.TextField, fields.UnicodeField))

    def test_bytes_field(self):
        f = fields.BytesField()
        f.value = 2
        self.assertEqual(f.value, b'2')
        self.assertTrue(isinstance(f.value, bytes))
        f.value = 'abc'
        self.assertEqual(f.value, b'abc')
        self.assertTrue(isinstance(f.value, bytes))

    def test_integer_field(self):
        f = fields.IntegerField()
        f.value = 1
        self.assertEqual(f.value, 1)
        f.value = 0b1
        self.assertEqual(f.value, 1)
        f.value = 0x1
        self.assertEqual(f.value, 1)
        f.value = 0o1
        self.assertEqual(f.value, 1)
        f.value = '1'
        self.assertEqual(f.value, 1)
        f.value = 1.0
        self.assertEqual(f.value, 1)
        with self.assertRaises(FileMakerValidationError):
            f.value = 'a'

    def test_float_field(self):
        f = fields.FloatField()
        f.value = 1
        self.assertEqual(f.value, 1.0)
        f.value = 0b1
        self.assertEqual(f.value, 1.0)
        f.value = 0x1
        self.assertEqual(f.value, 1.0)
        f.value = 0o1
        self.assertEqual(f.value, 1.0)
        f.value = '1'
        self.assertEqual(f.value, 1.0)
        f.value = '1.0'
        self.assertEqual(f.value, 1.0)
        f.value = 1.0
        self.assertEqual(f.value, 1.0)
        with self.assertRaises(FileMakerValidationError):
            f.value = 'a'

    def test_decimal_field(self):
        f = fields.FloatField()
        f.value = Decimal('1')
        self.assertEqual(f.value, Decimal('1'))
        f.value = 1
        self.assertEqual(f.value, Decimal('1'))
        f.value = 0b1
        self.assertEqual(f.value, Decimal('1'))
        f.value = 0x1
        self.assertEqual(f.value, Decimal('1'))
        f.value = 0o1
        self.assertEqual(f.value, Decimal('1'))
        f.value = '1'
        self.assertEqual(f.value, Decimal('1'))
        f.value = '1.0'
        self.assertEqual(f.value, Decimal('1.0'))
        f.value = 1.0
        self.assertEqual(f.value, Decimal('1.0'))
        with self.assertRaises(FileMakerValidationError):
            f.value = 'a'

    def test_decimal_field_decimal_places(self):
        f = fields.DecimalField(decimal_places=2)
        f.value = Decimal('1.219')
        self.assertEqual(f.value, Decimal('1.22'))
        f = fields.DecimalField(decimal_places=5)
        f.value = Decimal('1.219')
        self.assertEqual(f.value, Decimal('1.21900'))

    @override_settings(USE_TZ=False)
    def test_datetime_field_naive(self):
        now = timezone.now()
        assert timezone.is_naive(now)
        aware = timezone.make_aware(now, timezone.get_current_timezone())
        f = fields.DateTimeField()
        f.value = aware
        self.assertEqual(now, f.value)

    @override_settings(USE_TZ=True)
    def test_datetime_field_aware(self):
        now = timezone.now()
        assert timezone.is_aware(now)
        naive = timezone.make_naive(now, timezone.get_current_timezone())
        f = fields.DateTimeField()
        f.value = naive
        self.assertEqual(now, f.value)

    def test_datetime_field_combine(self):
        now = timezone.now()
        f = fields.DateTimeField()
        f.value = now.date()
        self.assertEqual(f.value.date(), now.date())
        self.assertTrue(isinstance(f.value, datetime.datetime))
        self.assertEqual(f.value.time(), datetime.time.min)
        f = fields.DateTimeField(combine_datetime=datetime.time.max)
        f.value = now.date()
        self.assertEqual(f.value.date(), now.date())
        self.assertTrue(isinstance(f.value, datetime.datetime))
        self.assertEqual(f.value.time(), datetime.time.max)
        f = fields.DateTimeField(combine_datetime=datetime.time(12, 30))
        f.value = now.date()
        self.assertEqual(f.value.date(), now.date())
        self.assertTrue(isinstance(f.value, datetime.datetime))
        self.assertEqual(f.value.time(), datetime.time(12, 30))

    def test_datetime_field_strptime(self):
        f = fields.DateTimeField(strptime='%Y %d %m %H')
        f.value = '2012 11 02 12'
        d = f.value
        self.assertEqual(d.year, 2012)
        self.assertEqual(d.month, 2)
        self.assertEqual(d.day, 11)
        self.assertEqual(d.hour, 12)
        self.assertTrue(isinstance(d, datetime.datetime))

    def test_datetime_field_parse(self):
        f = fields.DateTimeField()
        f.value = '2012 Jan 3rd 12:30'
        d = f.value
        self.assertEqual(d.year, 2012)
        self.assertEqual(d.month, 1)
        self.assertEqual(d.day, 3)
        self.assertEqual(d.hour, 12)
        self.assertEqual(d.minute, 30)
        self.assertTrue(isinstance(d, datetime.datetime))
        f.value = '20120103123002'
        d = f.value
        self.assertEqual(d.year, 2012)
        self.assertEqual(d.month, 1)
        self.assertEqual(d.day, 3)
        self.assertEqual(d.hour, 12)
        self.assertEqual(d.minute, 30)
        self.assertEqual(d.second, 2)
        self.assertTrue(isinstance(d, datetime.datetime))

    @override_settings(USE_TZ=False)
    def test_datetime_parse_overflow(self):
        '''
        We get a problem with a particular datetime format using dateutils
        parse. We should recover using strptime.
        '''
        f = fields.DateTimeField()
        f.value = '2012622100000'
        self.assertEqual(f.value, datetime.datetime(2012, 6, 22, 10, 0))

    def test_datetime_field_iterable(self):
        f = fields.DateTimeField()
        f.value = (2012, 1, 3, 12, 30, 2)
        d = f.value
        self.assertEqual(d.year, 2012)
        self.assertEqual(d.month, 1)
        self.assertEqual(d.day, 3)
        self.assertEqual(d.hour, 12)
        self.assertEqual(d.minute, 30)
        self.assertEqual(d.second, 2)
        self.assertTrue(isinstance(d, datetime.datetime))
        f.value = [2012, 1, 3, 12, 30, 2]
        self.assertEqual(f.value, d)

    def test_datetime_field_number(self):
        now = timezone.now().replace(microsecond=0)
        now_t = time.mktime(now.timetuple())
        f = fields.DateTimeField()
        f.value = now_t
        self.assertEqual(f.value, now)
        now_t = int(now_t)
        f.value = now_t
        self.assertEqual(f.value, now)

    def test_datetime_field_raises(self):
        f = fields.DateTimeField()
        with self.assertRaises(FileMakerValidationError):
            f.value = {}

    def test_datetime_field_raises_on_empty_string(self):
        # dateutil's parser will turn an empty string into now, we don't
        # want this
        f = fields.DateTimeField()
        with self.assertRaises(FileMakerValidationError):
            f.value = ''

    def test_datetime_field_to_filemaker(self):
        f = fields.DateTimeField(null=True)
        f.value = None
        self.assertEqual(f.to_filemaker(), '')
        now = timezone.now()
        f.value = now
        self.assertEqual(f.to_filemaker(), now.isoformat())

    @override_settings(USE_TZ=False)
    def test_date_field_no_tz(self):
        f = fields.DateField()
        now = timezone.now()
        f.value = now
        self.assertEqual(f.value, now.date())

    def test_date_field_to_filemaker(self):
        f = fields.DateField(null=True)
        f.value = None
        self.assertEqual(f.to_filemaker(), '')
        now = timezone.now().date()
        f.value = now
        self.assertEqual(f.to_filemaker(), now.isoformat())

    @override_settings(USE_TZ=True)
    def test_date_field(self):
        f = fields.DateField()
        now = timezone.now()
        f.value = now
        self.assertEqual(f.value, now.date())

    def test_boolean_field(self):
        f = fields.BooleanField()
        for val in [True, 1, -1, 1., 'y', 'yes', 'true', 't', '1', [1], (1,)]:
            f.value = val
            self.assertTrue(f.value)
        for val in [False, 0, 0., 'n', 'no', 'false', 'f', '0', [], ()]:
            f.value = val
            self.assertFalse(f.value)

    def test_boolean_field_map(self):
        f = fields.BooleanField(map={'ja': True, 'nein': False})
        f.value = 'ja'
        self.assertTrue(f.value)
        f.value = 'nein'
        self.assertFalse(f.value)

    def test_null_boolean_field(self):
        f = fields.NullBooleanField()
        self.assertEqual(f.coerce(None), None)
        self.assertEqual(f.coerce('None'), None)

    def test_boolean_field_to_filemaker(self):
        f = fields.BooleanField(null=True)
        f.value = None
        self.assertEqual(f.to_filemaker(), '')
        f.value = True
        self.assertEqual(f.to_filemaker(), 'true')
        f.value = False
        self.assertEqual(f.to_filemaker(), 'false')
        f = fields.BooleanField(map={'ja': True, 'nein': False})
        f.value = True
        self.assertEqual(f.to_filemaker(), 'ja')
        f.value = False
        self.assertEqual(f.to_filemaker(), 'nein')

    def test_list_field(self):
        with self.assertRaises(ValueError):
            f = fields.ListField()
        f = fields.ListField(base_type=fields.IntegerField)
        with self.assertRaises(FileMakerValidationError):
            f.value = ['a', 'b', 'c']
        f.value = [1, 2, 3]
        self.assertEqual(f.value, [1, 2, 3])
        self.assertEqual(f.to_django(), [1, 2, 3])

    def test_list_field_to_filemaker(self):
        f = fields.ListField(base_type=fields.IntegerField)
        f.value = [1, 2, 3]
        self.assertEqual(f.to_filemaker(), ['1', '2', '3'])

    def test_model_field(self):
        class TestFMModel(FileMakerModel):
            name = fields.CharField('name')
            value = fields.IntegerField('value')

        fm_value = Mock()
        fm_value.name = 'Name'
        fm_value.value = 123
        f = fields.ModelField(model=TestFMModel)
        f.value = fm_value
        self.assertEqual(f.value.name, 'Name')
        self.assertEqual(f.value.value, 123)
        fm_value.value = 'a'
        with self.assertRaises(FileMakerValidationError):
            f.value = fm_value
        f.null = True
        f.value = fm_value
        self.assertEqual(f.value, None)
        f.default = 1
        f.value = fm_value
        self.assertEqual(f.value, 1)

    def test_model_field_to_filemaker(self):
        class TestFMModel(FileMakerModel):
            name = fields.CharField('name')
            value = fields.IntegerField('value')

            def to_filemaker(self):
                return self.name, self.value

        fm_value = Mock()
        fm_value.name = 'Name'
        fm_value.value = 123
        f = fields.ModelField(model=TestFMModel)
        f.value = fm_value
        self.assertEqual(f.to_filemaker(), ('Name', 123))

    def test_model_list_field(self):
        class TestFMModel(FileMakerModel):
            name = fields.CharField('name')
            value = fields.IntegerField('value')

        fm_value = Mock()
        fm_value.name = 'Name'
        fm_value.value = 123
        f = fields.ModelListField(model=TestFMModel)
        f.value = [fm_value, fm_value]
        self.assertEqual(len(f.value), 2)
        for val in f.value:
            self.assertEqual(val.name, 'Name')
            self.assertEqual(val.value, 123)
        fm_value.value = 'a'
        with self.assertRaises(FileMakerValidationError):
            f.value = [fm_value, fm_value]

    def test_model_list_field_to_filemaker(self):
        class TestFMModel(FileMakerModel):
            name = fields.CharField('name')
            value = fields.IntegerField('value')

            def to_filemaker(self):
                return self.name, self.value

        fm_value = Mock()
        fm_value.name = 'Name'
        fm_value.value = 123
        f = fields.ModelListField(model=TestFMModel)
        f.value = [fm_value]
        self.assertEqual(f.to_filemaker(), [('Name', 123)])

    def test_rel_synonyms(self):
        self.assertTrue(issubclass(fields.ToOneField, fields.ModelField))
        self.assertTrue(issubclass(fields.ToManyField, fields.ModelListField))

    def test_percentage_field(self):
        f = fields.PercentageField()
        with self.assertRaises(FileMakerValidationError):
            f.value = '-1'
        with self.assertRaises(FileMakerValidationError):
            f.value = '101'
        f.value = '50'
        self.assertIn('%', text_type(f))

    def test_currency_field(self):
        f = fields.CurrencyField()
        f.value = '2'
        self.assertEqual(f.value, Decimal('2.00'))
        f.value = '$19.99'
        self.assertEqual(f.value, Decimal('19.99'))
        with self.assertRaises(FileMakerValidationError):
            f.value = '-1'

    def test_slug_field(self):
        f = fields.SlugField()
        f.value = 'A Test Slug'
        self.assertEqual(f.value, 'a-test-slug')
        f = fields.SlugField(auto=False)
        with self.assertRaises(FileMakerValidationError):
            f.value = 'a %1 )('
        f.value = 'a-test-slug'
        self.assertEqual(f.value, 'a-test-slug')
        f = fields.SlugField(slugify=lambda x: 'aaa')
        f.value = 'Test Value'
        self.assertEqual(f.value, 'aaa')

    def test_null_values(self):
        # This should raise a value error because for a decimal field ''
        # is a null value and null is not True
        f = fields.DecimalField()
        with self.assertRaises(FileMakerValidationError):
            f.value = ''
        # And this should be allowed, and return a value of None
        f = fields.DecimalField(null=True)
        f.value = ''
        self.assertEqual(f.value, None)

    def test_can_create_model_list_field_with_instances(self):
        class TestModel(FileMakerModel):
            f = fields.CharField()
        f = fields.ModelListField(model=TestModel)
        f.value = [TestModel(f='abc')]
        self.assertEqual(f.value, [TestModel(f='abc')])

    def test_gtin_field(self):
        test_values = (
            ('0', False),
            ('01', False),
            ('012', False),
            ('0123', False),
            ('01234', False),
            ('012345', True),
            ('01a345', False),
            ('0123456', True),
            ('0123z56', False),
            ('01234567', True),
            ('01234b67', False),
            ('012345678', False),
            ('0123456789', True),
            ('0c23456789', False),
            ('01234567890', False),
            ('012345678901', True),
            ('01234567d901', False),
            ('0123456789012', True),
            ('012e456789012', False),
            ('01234567890123', True),
            ('012e4567890123', False),
            ('012345678901234', True),
            ('012e45678901234', False),
            ('0123456789012345', True),
            ('012e456789012345', False),
        )
        f = fields.GTINField()
        for val, validate in test_values:
            if validate:
                f.value = val
                self.assertEqual(f.value, val)
            else:
                with self.assertRaises(FileMakerValidationError):
                    f.value = val

    @patch('filemaker.fields.FileField._get_file')
    def test_image_field(self, get):
        get.return_value.content_type = 'text/plain'
        with self.assertRaises(FileMakerValidationError):
            fields.ImageField()._get_file('')
        get.return_value.content_type = 'image/jpg'
        self.assertEqual(fields.ImageField()._get_file(''), get.return_value)

    def test_file_field_init(self):
        field = fields.FileField()
        self.assertTrue(isinstance(field.base_url, urlobject.URLObject))
        self.assertEqual(text_type(field.base_url), '')
        field = fields.FileField(base_url='http://google.com/')
        self.assertTrue(isinstance(field.base_url, urlobject.URLObject))
        self.assertEqual(text_type(field.base_url), 'http://google.com/')

    @httprettified
    def test_file_field_get_http(self):
        url = 'http://example.com/logo.jpg'
        HTTPretty.register_uri(
            HTTPretty.GET,
            url,
            responses=[
                HTTPretty.Response(body='', status=404),
                HTTPretty.Response(
                    body='monkeys', status=200,
                    content_type='text/html; charset=utf-8'),
                HTTPretty.Response(
                    body='I am totally an image', status=200,
                    content_type='image/jpg'),
            ]
        )
        url = urlobject.URLObject(url)
        field = fields.FileField()
        # Error response
        self.assertEqual(field._get_http(url), (None, None))
        # Content-Type with charset
        self.assertEqual(field._get_http(url), (b'monkeys', 'text/html'))
        # Normal
        self.assertEqual(
            field._get_http(url), (b'I am totally an image', 'image/jpg'))

    def test_file_field_get_file_invalid_scheme(self):
        field = fields.FileField()
        with self.assertRaises(FileMakerValidationError):
            url = urlobject.URLObject(
                'sftp://user:pass@domain.com/path/to/file.jpg')
            field._get_file(url)

    @httprettified
    def test_file_field_get_file_download_failure(self):
        url = 'http://example.com/image.jpg'
        HTTPretty.register_uri(HTTPretty.GET, url, body='', status=404)
        field = fields.FileField()
        with self.assertRaises(FileMakerValidationError):
            url = urlobject.URLObject(url)
            field._get_file(url)

    @httprettified
    def test_file_field_get_file_normalises_jpg_type(self):
        field = fields.FileField()
        url = urlobject.URLObject('http://example.com/image.jpg')
        for mime in ('image/jpeg', 'image/jpe', 'image/jpeg'):
            HTTPretty.register_uri(
                HTTPretty.GET, text_type(url), body='', status=200,
                content_type=mime)
            uploaded = field._get_file(url)
            self.assertEqual(uploaded['content-type'], 'image/jpg')
            self.assertTrue(uploaded['filename'].endswith('.jpg'))

    @httprettified
    def test_file_field_get_file_success(self):
        field = fields.FileField()
        url = urlobject.URLObject('http://example.com/file.txt')
        HTTPretty.register_uri(
            HTTPretty.GET, text_type(url), body='I am text', status=200,
            content_type='text/plain')
        uploaded = field._get_file(url)
        self.assertEqual(uploaded['content-type'], 'text/plain')
        self.assertEqual(uploaded['content'], b'I am text')

    def test_file_field_coerce(self):
        field = fields.FileField()
        with patch.object(field, '_get_file') as get:
            get.side_effect = lambda url: url
            # Add scheme, auth, and domain if missing
            field.base_url = urlobject.URLObject('http://user:pass@domain.com')
            self.assertEqual(
                text_type(field.coerce('/image.jpg')),
                'http://user:pass@domain.com/image.jpg'
            )
            # Otherwise leave as is...
            self.assertEqual(
                field.coerce('http://username:password@example.com/test.jpg'),
                'http://username:password@example.com/test.jpg',
            )

    @httprettified
    def test_file_field_to_django(self):
        field = fields.FileField()
        url = urlobject.URLObject('http://example.com/file.txt')
        HTTPretty.register_uri(
            HTTPretty.GET, text_type(url), body='I am text', status=200,
            content_type='text/plain')
        field.value = 'http://example.com/file.txt'
        djuploaded = field.to_django()
        self.assertEqual(djuploaded.content_type, 'text/plain')
        self.assertEqual(djuploaded.read(), b'I am text')

    @httprettified
    def test_file_field_to_filemaker(self):
        storage = Mock()
        field = fields.FileField(null=True, storage=storage)
        self.assertEqual(field.to_filemaker(), '')
        url = urlobject.URLObject('http://example.com/file.txt')
        HTTPretty.register_uri(
            HTTPretty.GET, text_type(url), body='I am text', status=200,
            content_type='text/plain')
        field.value = 'http://example.com/file.txt'
        storage.url.return_value = '/some/url'
        self.assertEqual(field.to_filemaker(), '/some/url')

    def test_file_field_no_value(self):
        field = fields.FileField(null=True)
        self.assertEqual(None, field.to_django())

    def test_uploaded_file_field_to_django(self):
        f = Mock()
        f.name = 'some_name.txt'
        storage = Mock()
        storage.open.return_value = f
        field = fields.UploadedFileField(storage=storage)
        field.value = 'some_name.txt'
        self.assertEqual(field.to_django(), f)
        field = fields.UploadedFileField(null=True)
        field.value = None
        self.assertEqual(field.to_django(), None)

    def test_uploaded_file_field_to_filemaker(self):
        f = Mock()
        f.name = 'some_name.txt'
        storage = Mock()
        storage.open.return_value = f
        field = fields.UploadedFileField(null=True, storage=storage)
        field.value = None
        self.assertEqual(field.to_filemaker(), '')
        field.value = 'some_name.txt'
        storage.url.return_value = '/media/some_file.txt'
        self.assertEqual(field.to_filemaker(), '/media/some_file.txt')

    def test_uploaded_file_field_coerce(self):
        f = Mock()
        f.name = 'some_name.txt'
        storage = Mock()
        storage.open.return_value = f
        field = fields.UploadedFileField(storage=storage)
        self.assertEqual(
            field.coerce('some_name.txt'),
            {'file': f, 'filename': f.name},
        )
        storage.open.side_effect = Exception
        with self.assertRaises(FileMakerValidationError):
            field.coerce('some_name.txt')


@override_settings(INSTALLED_APPS=['django.contrib.sites',
                                   'django.contrib.flatpages'])
class TestFilemakerBase(TransactionTestCase):

    def test_meta_assignment(self):

        class TestMetaModel(FileMakerModel):

            meta = {
                'django_pk_name': 'id',
                'something': 'else',
            }

        instance = TestMetaModel()
        self.assertFalse(hasattr(instance, 'meta'))
        self.assertTrue(hasattr(instance, '_meta'))
        fields = [
            'connection',
            'pk_name',
            'django_pk_name',
            'django_model',
            'django_field_map',
            'abstract',
            'something',
        ]
        for field in fields:
            self.assertIn(field, instance._meta)
            self.assertEqual(instance._meta['django_pk_name'], 'id')

    def test_meta_assignment_no_dict(self):

        class TestMetaModel(FileMakerModel):
            meta = 'pk'

        instance = TestMetaModel()
        self.assertFalse(hasattr(instance, 'meta'))
        self.assertTrue(hasattr(instance, '_meta'))

    def test_fields_assignment(self):

        class TestFieldsModel(FileMakerModel):
            name = fields.CharField('name')
            value = fields.IntegerField('value')
            not_a_field = 10

        instance = TestFieldsModel()
        self.assertTrue(hasattr(instance, '_fields'))
        self.assertIn('name', instance._fields)
        self.assertIn('value', instance._fields)
        self.assertNotIn('not_a_field', instance._fields)
        for val in instance._fields.values():
            self.assertTrue(isinstance(val, fields.BaseFileMakerField))
        instance.name = 'key'
        self.assertEqual(instance.name, 'key')
        self.assertEqual(instance._fields['name'].value, 'key')
        with self.assertRaises(FileMakerValidationError):
            instance.value = 'a'
        self.assertEqual(instance.not_a_field, 10)
        instance.not_a_field = 20
        self.assertEqual(instance.not_a_field, 20)

    def test_init_with_obj(self):

        class TestInitModel(FileMakerModel):
            name = fields.CharField('name')
            value = fields.IntegerField('value')

        fm_obj = Mock()
        fm_obj.name = 'Test'
        fm_obj.value = 42
        instance = TestInitModel(fm_obj)
        self.assertEqual(instance.name, 'Test')
        self.assertEqual(instance.value, 42)
        self.assertEqual(instance._fm_obj, fm_obj)

    def test_simple_model_to_django(self):

        mock_fm_site = Mock()
        mock_fm_site.name = 'Test'
        mock_fm_site.domain = 'test.tld'
        mock_fm_site.id = 3

        class TestFMSite(FileMakerModel):
            id = fields.IntegerField('id')
            name = fields.CharField('name')
            domain = fields.CharField('domain')

            meta = {'model': Site}

        instance = TestFMSite(mock_fm_site)
        site = instance.to_django()
        self.assertTrue(Site.objects
                        .filter(name='Test', domain='test.tld', pk=3).exists())
        self.assertTrue(isinstance(site, Site))
        site.delete()
        site = instance.to_django()
        self.assertTrue(isinstance(site, Site))
        self.assertTrue(
            Site.objects.filter(name='Test', domain='test.tld', pk=3).exists())

    def test_model_to_django_existing(self):

        Site.objects.create(pk=3, name='Change Me', domain='wrong.tld')
        mock_fm_site = Mock()
        mock_fm_site.name = 'Test'
        mock_fm_site.domain = 'test.tld'
        mock_fm_site.id = 3

        class TestFMSite(FileMakerModel):
            id = fields.IntegerField('id')
            name = fields.CharField('name')
            domain = fields.CharField('domain')

            meta = {'model': Site}

        instance = TestFMSite(mock_fm_site)
        site = instance.to_django()
        self.assertTrue(Site.objects
                        .filter(name='Test', domain='test.tld', pk=3).exists())
        self.assertTrue(isinstance(site, Site))

    def test_model_to_django_meta_abstract(self):
        mock_fm_site = Mock()
        mock_fm_site.name = 'Test'
        mock_fm_site.domain = 'test.tld'
        mock_fm_site.id = 3

        class TestFMSite(FileMakerModel):
            pk = fields.IntegerField('id')
            name = fields.CharField('name')
            domain = fields.CharField('domain')

            meta = {'model': Site, 'abstract': True}

        instance = TestFMSite(mock_fm_site)
        site = instance.to_django()
        self.assertTrue(isinstance(site, Site))
        self.assertTrue(
            Site.objects.filter(name='Test', domain='test.tld', pk=3).exists())

    def test_model_to_django_meta_model(self):
        mock_fm_site = Mock()
        mock_fm_site.name = 'Test'
        mock_fm_site.domain = 'test.tld'
        mock_fm_site.id = 3

        class TestFMSite(FileMakerModel):
            pk = fields.IntegerField('id')
            name = fields.CharField('name')
            domain = fields.CharField('domain')

            meta = {}
        instance = TestFMSite(mock_fm_site)
        self.assertEqual(instance.to_django(), None)

    def test_model_to_django_pk_name(self):
        mock_fm_site = Mock()
        mock_fm_site.name = 'Test'
        mock_fm_site.domain = 'test.tld'
        mock_fm_site.id = 3

        class TestFMSite(FileMakerModel):
            name = fields.CharField('name')
            domain = fields.CharField('domain')

            meta = {
                'model': Site,
                'pk_name': None,
            }
        instance = TestFMSite(mock_fm_site)
        site = instance.to_django()
        self.assertNotEqual(site.pk, None)

    def test_model_to_django_meta_django_field_map(self):
        mock_fm_site = Mock()
        mock_fm_site.name = 'Test'
        mock_fm_site.domain = 'test.tld'
        mock_fm_site.id = None

        class TestFMSite(FileMakerModel):
            id = fields.IntegerField('id', null=True)
            name = fields.CharField('name')
            domain = fields.CharField('domain')

            meta = {
                'model': Site,
                'django_field_map': (
                    ('name', 'domain'),
                    ('domain', 'name'),
                ),
            }
        instance = TestFMSite(mock_fm_site)
        site = instance.to_django()
        self.assertEqual(site.domain, 'Test')
        self.assertEqual(site.name, 'test.tld')
        self.assertNotEqual(site.pk, None)

    def test_to_one_relations(self):

        mock_fm_site = Mock()
        mock_fm_site.name = 'Test'
        mock_fm_site.domain = 'test.tld'
        mock_fm_site.id = 3

        mock_fm_redirect = Mock()
        mock_fm_redirect.site = mock_fm_site
        mock_fm_redirect.old_path = '/old-path/'
        mock_fm_redirect.new_path = '/new-path/'

        class TestFMSite(FileMakerModel):
            id = fields.IntegerField('id', null=True)
            name = fields.CharField('name')
            domain = fields.CharField('domain')

            meta = {
                'model': Site,
                'abstract': True,
            }

        class TestFMRedirect(FileMakerModel):
            old_path = fields.CharField('old_path')
            new_path = fields.CharField('new_path')
            site = fields.ModelField('site', model=TestFMSite)

            meta = {
                'model': Redirect,
            }

        instance = TestFMRedirect(mock_fm_redirect)
        instance.to_django(save=True)
        self.assertTrue(
            Redirect.objects.filter(site__id=3, site__name='Test',
                                    site__domain='test.tld',
                                    old_path='/old-path/',
                                    new_path='/new-path/').exists()
        )

    def test_to_many_relations(self):
        from django.contrib.flatpages.models import FlatPage
        # syncdb in case flatpages isn't installed
        call_command('syncdb', interactive=False)
        mock_fm_site = NonCallableMock()
        mock_fm_site.name = 'Test'
        mock_fm_site.domain = 'test.tld'
        mock_fm_site.id = 3
        mock_fm_site_2 = NonCallableMock()
        mock_fm_site_2.name = 'Test2'
        mock_fm_site_2.domain = 'test2.tld'
        mock_fm_site_2.id = 4

        mock_fm_flatpage = NonCallableMagicMock()
        mock_fm_flatpage.sites = [mock_fm_site, mock_fm_site_2]
        mock_fm_flatpage.content = 'Content'
        mock_fm_flatpage.title = 'Title'
        mock_fm_flatpage.url = '/url/'

        class TestFMSite(FileMakerModel):
            id = fields.IntegerField('id', null=True)
            name = fields.CharField('name')
            domain = fields.CharField('domain')

            meta = {
                'model': Site,
                'abstract': True,
            }

        class TestFMFlatPage(FileMakerModel):
            content = fields.CharField('content')
            title = fields.CharField('title')
            url = fields.CharField('url')
            sites = fields.ModelListField('sites', model=TestFMSite)

            meta = {
                'model': FlatPage,
            }

        instance = TestFMFlatPage(mock_fm_flatpage)
        instance.to_django(save=True)
        sites = Site.objects.filter(pk__in=[3, 4])
        self.assertEqual(sites.count(), 2)
        self.assertTrue(
            FlatPage.objects.filter(sites__in=sites, content='Content',
                                    title='Title', url='/url/').exists()
        )
        FlatPage.objects.all().delete()
        instance._meta['to_many_action'] = ''
        instance.to_django(save=True)
        sites = Site.objects.filter(pk__in=[3, 4])
        self.assertEqual(sites.count(), 2)
        self.assertTrue(
            FlatPage.objects.filter(sites__in=sites, content='Content',
                                    title='Title', url='/url/').exists()
        )
        FlatPage.objects.all().delete()

    def test_to_dict(self):

        class DictTestToOneModel(FileMakerModel):
            to_one_name = fields.CharField('to_one_name')

        class DictTestToManyModel(FileMakerModel):
            to_many_name = fields.CharField()

        class DictTestModel(FileMakerModel):
            name = fields.CharField()
            value = fields.IntegerField()
            to_one = fields.ModelField(model=DictTestToOneModel)
            to_many = fields.ModelListField(model=DictTestToManyModel)

        t_one = NonCallableMock()
        t_one.to_one_name = 'one'
        t_many = NonCallableMock()
        t_many.to_many_name = 'many'
        m = Mock()
        m.name = 'Name'
        m.value = 1
        m.to_one = t_one
        m.to_many = [t_many]
        instance = DictTestModel(m)
        d = instance.to_dict()
        self.assertDictEqual(
            d,
            {
                'name': 'Name',
                'value': 1,
                'to_one': {'to_one_name': 'one'},
                'to_many': [{'to_many_name': 'many'}],
            }
        )

    def test_fm_attr_initialisation(self):

        class TestModel(FileMakerModel):
            name = fields.CharField()
            value = fields.IntegerField('a_field')

        instance = TestModel()
        self.assertEqual(instance._fields['name'].fm_attr, 'name')
        self.assertEqual(instance._fields['value'].fm_attr, 'a_field')

    def test_independence(self):

        class TestModel(FileMakerModel):
            name = fields.CharField()
            value = fields.IntegerField()

        t1 = TestModel()
        t2 = TestModel()
        t1.name = 'Name'
        t2.name = 'Name2'
        t1.value = '1'
        t2.value = '2'
        permutations = \
            itertools.permutations([t1.name, t2.name, t1.value, t2.value], 2)
        for f1, f2 in permutations:
            self.assertNotEqual(f1, f2)

    def test_ordering_different_models(self):

        class TestModel(FileMakerModel):
            name = fields.CharField()
            value = fields.IntegerField()

        class TestModel2(FileMakerModel):
            name2 = fields.CharField()
            value2 = fields.IntegerField()

        with self.assertRaises(TypeError):
            TestModel() < TestModel2()

    def test_ordering_no_meta_ordering(self):

        class TestModel(FileMakerModel):
            name = fields.CharField()
            value = fields.IntegerField()

        class TestIDModel(FileMakerModel):
            id = fields.IntegerField()
            name = fields.CharField()
            value = fields.IntegerField()

        with self.assertRaises(ValueError):
            TestModel() < TestModel()

        t1 = TestIDModel(id=1)
        t2 = TestIDModel(id=2)
        self.assertTrue(t1 < t2)

    def test_ordering_meta(self):

        class TestModel(FileMakerModel):
            name = fields.CharField()
            value = fields.IntegerField()

            meta = {'ordering': 'name'}

        class TestReverseModel(FileMakerModel):
            name = fields.CharField()
            value = fields.IntegerField()

            meta = {'ordering': '-name'}

        t1 = TestModel(name='a')
        t2 = TestModel(name='b')
        self.assertTrue(t1 < t2)
        tr1 = TestReverseModel(name='a')
        tr2 = TestReverseModel(name='b')
        self.assertTrue(tr1 > tr2)

    def test_deep_getattr(self):
        obj = Mock()
        obj.exodus = 'metal'
        obj.narwhal.bacon = 'midnight'
        obj.warning = 1
        with self.assertRaises(ValueError):
            deep_getattr(obj, None)
        with self.assertRaises(ValueError):
            deep_getattr(obj, '')
        self.assertEqual(obj, deep_getattr(obj, '+self'))
        self.assertEqual('metal', deep_getattr(obj, 'exodus'))
        self.assertEqual('midnight', deep_getattr(obj, 'narwhal.bacon'))
        self.assertEqual(None, deep_getattr(obj, 'warning.monkeyspunk'))


class TestRawManager(TransactionTestCase):

    def setUp(self):
        connection = {
            'db': 'db_name',
            'url': 'http://user:pass@domain.com/',
            'layout': 'layout_name',
            'response_layout': 'response_layout_name',
        }
        self.manager = RawManager(**connection)

    def test_init(self):
        connection = {
            'db': 'db_name',
            'url': 'http://user:pass@domain.com/',
            'layout': 'layout_name',
            'response_layout': 'response_layout_name',
        }
        manager = RawManager(**connection)
        self.assertEqual(manager.url, 'http://domain.com/')
        self.assertEqual(manager.auth, ('user', 'pass'))

    def test_set_script(self):
        mgr = self.manager.set_script('some_script')
        self.assertEqual(mgr.params['-script'], 'some_script')
        mgr = self.manager.set_script('some_script', 'prefind')
        self.assertEqual(mgr.params['-script.prefind'], 'some_script')

    def test_set_record_id(self):
        mgr = self.manager.set_record_id(1)
        self.assertEqual(mgr.params['-recid'], 1)

    def test_set_modifier_id(self):
        mgr = self.manager.set_modifier_id(1)
        self.assertEqual(mgr.params['-modid'], 1)

    def test_set_logical_operator(self):
        mgr = self.manager.set_logical_operator('and')
        self.assertEqual(mgr.params['-lop'], 'and')

    def test_set_group_size(self):
        mgr = self.manager.set_group_size(5)
        self.assertEqual(mgr.params['-max'], 5)

    def test_skip_records(self):
        mgr = self.manager.set_skip_records(5)
        self.assertEqual(mgr.params['-skip'], 5)

    def test_add_db_param(self):
        mgr = self.manager.add_db_param('foo', 'bar')
        self.assertEqual(mgr.params['foo'], 'bar')
        mgr = self.manager.add_db_param('foo', 'bar', 'neq')
        self.assertEqual(mgr.params['foo'], 'bar')
        self.assertEqual(mgr.params['foo.op'], 'neq')

    def test_add_sort_param(self):
        mgr = self.manager.add_sort_param('foo')
        self.assertEqual(mgr.params['-sortfield.0'], 'foo')
        self.assertEqual(mgr.params['-sortorder.0'], 'ascend')


class TestFileMakerSubModel(FileMakerModel):

    index = fields.IntegerField('Sub_Index')


class TestFileMakerSubModelOnSelf(FileMakerModel):

    pub_date = fields.DateField('Publication')


class TestFileMakerMainModel(FileMakerModel):

    text = fields.CharField('Item_Text')
    subs = fields.ModelListField('SUB_ITEMS', model=TestFileMakerSubModel)
    pubs = fields.ModelField('+self', model=TestFileMakerSubModelOnSelf)

    meta = {
        'connection': {
            'db': 'db_name',
            'url': 'http://user:pass@domain.com/',
            'layout': 'layout_name',
        },
    }


class TestManager(TransactionTestCase):

    def setUp(self):
        connection = {
            'db': 'db_name',
            'url': 'http://user:pass@domain.com/',
            'layout': 'layout_name',
            'response_layout': 'response_layout_name',
        }
        self.cls = MagicMock()
        self.cls._meta = {'connection': connection}
        self.cls.DoesNotExist = Exception
        self.manager = Manager(self.cls)

    def test_len(self):
        fm_data = MagicMock(resultset=[1, 2, 3])
        self.manager._fm_data = fm_data
        self.assertEqual(len(self.manager), 3)
        self.assertEqual(self.manager.count(), 3)

    def test_invalid_get_item_or_slice(self):
        with self.assertRaises(TypeError):
            self.manager['a']
        with self.assertRaises(AssertionError):
            self.manager[-1]

    def test_get_item(self):
        fm_data = MagicMock(resultset=[1, 2, 3])
        self.cls.side_effect = ['first', 'second', 'third']
        self.manager._fm_data = fm_data
        self.assertEqual('first', self.manager[0])

    def test_slice_a(self):
        fm_data = MagicMock(resultset=[1, 2, 3])
        self.cls.side_effect = ['first', 'second', 'third']
        self.manager._fm_data = fm_data
        self.assertEqual(['first', 'second'], self.manager[0:2])
        self.assertEqual(self.manager.params['-max'], 2)

    def test_slice_b(self):
        fm_data = MagicMock(resultset=[1, 2, 3])
        self.cls.side_effect = ['first', 'second', 'third']
        self.manager._fm_data = fm_data
        self.assertEqual(['second', 'third'], self.manager[1:3])
        self.assertEqual(self.manager.params['-max'], 2)
        self.assertEqual(self.manager.params['-skip'], 1)

    def test_resolve_fm_field(self):
        mgr = TestFileMakerMainModel.objects
        self.assertEqual(
            mgr._resolve_fm_field('text'),
            'Item_Text'
        )
        self.assertEqual(
            mgr._resolve_fm_field('subs__index'),
            'SUB_ITEMS::Sub_Index'
        )
        self.assertEqual(
            mgr._resolve_fm_field('pubs__pub_date'),
            'Publication'
        )
        with self.assertRaises(ValueError):
            mgr._resolve_fm_field('i-m__not__a__field__i-m__a__free__man')
        with self.assertRaises(ValueError):
            mgr._resolve_fm_field('menofield')
        with self.assertRaises(ValueError):
            mgr._resolve_fm_field('subs__busted')

    def test_preprocess_resultset(self):
        # This should be a no-op but may as well test to make sure
        self.assertEqual(123, self.manager.preprocess_resultset(123))

    def test_all(self):
        # This should just return a clone of the manager
        new_mgr = self.manager.all()
        self.assertEqual(new_mgr.__dict__, self.manager.__dict__)

    def test_filter_basic(self):
        mgr = TestFileMakerMainModel.objects.filter(text='crazy text')
        self.assertEqual(
            dict(mgr.params),
            dict(QueryDict('Item_Text.op=eq&-max=50&Item_Text=crazy%20text'))
        )

    def test_filter_with_op(self):
        mgr = TestFileMakerMainModel.objects.filter(
            pubs__pub_date__lt=datetime.date(1999, 12, 31))
        self.assertEqual(
            dict(QueryDict(mgr.params.urlencode())),
            dict(QueryDict('-max=50&Publication=1999-12-31&Publication.op=lt'))
        )

    def test_filter_failure(self):
        with self.assertRaises(ValueError):
            TestFileMakerMainModel.objects.filter(whatwhat=123)
        with self.assertRaises(ValueError):
            TestFileMakerMainModel.objects.filter(pubs__pub_date__noop=123)

    def test_manager_not_available_from_instance(self):
        fmm = TestFileMakerMainModel()
        with self.assertRaises(AttributeError):
            fmm.objects

    def test_get(self):
        with patch.object(self.manager, 'filter') as fltr:
            fltr.return_value = [1, 2, 3]
            self.assertEqual(self.manager.get(pk=123), 1)
            fltr.assert_called_with(pk=123)
            fltr.reset_mock()
            fltr.return_value = []
            with self.assertRaises(self.cls.DoesNotExist):
                self.manager.get(pk=123)

    def test_order_by(self):
        mgr = TestFileMakerMainModel.objects.order_by('text')
        self.assertEqual(
            dict(mgr.params),
            dict(QueryDict(
                '-max=50&-sortorder.0=ascend&-sortfield.0=Item_Text'))
        )
        mgr = mgr.order_by('pubs__pub_date', '-text')
        self.assertEqual(
            dict(mgr.params),
            dict(QueryDict(
                '-sortfield.1=Item_Text&-max=50&-sortorder.0=ascend&'
                '-sortorder.1=descend&-sortfield.0=Publication'))
        )
        mgr = mgr.order_by('-pubs__pub_date')
        self.assertEqual(
            dict(mgr.params),
            dict(QueryDict(
                '-max=50&-sortorder.0=descend&-sortfield.0=Publication'))
        )


class TestUtils(TransactionTestCase):

    @override_settings(FILEMAKER_DJANGO_FIELD_MAP={
        CharField: fields.CharField,
        IntegerField: 'filemaker.fields.IntegerField',
    })
    def test_get_field_class(self):
        self.assertEqual(get_field_class(CharField), fields.CharField)
        self.assertEqual(get_field_class(CharField()), fields.CharField)
        self.assertEqual(
            get_field_class('django.db.models.fields.IntegerField'),
            fields.IntegerField
        )
