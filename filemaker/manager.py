# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import copy
import re

import requests
from django.http import QueryDict
from django.utils import six
from urlobject import URLObject

from .exceptions import FileMakerConnectionError
from .parser import FMXMLObject


OPERATORS = {
    'exact': 'eq',
    'contains': 'cn',
    'startswith': 'bw',
    'endswith': 'ew',
    'gt': 'gt',
    'gte': 'gte',
    'lt': 'lt',
    'lte': 'lte',
    'neq': 'neq',
}


class RawManager(object):
    '''
    The raw manager allows you to query the FileMaker web interface.

    Most manager methods (the exceptions being the committing methods;
    ``find``, ``find_all``, ``edit``, ``new``, and ``delete``) are chainable,
    enabling usage like
    ::

        manager = RawManager(...)
        manager = manager.filter(field=value).add_sort_param('some_field')
        results = manager.find_all()
    '''

    def __init__(self, url, db, layout, response_layout=None, **kwargs):
        '''
        :param url: The URL to access the FileMaker server. This should contain
            any authorization credentials. If a path is not provided (e.g. no
            trailing slash, like ``http://username:password@192.168.1.2``) then
            the default path of ``/fmi/xml/fmresultset.xml`` will be used.
        :param db: The database name to access (sets the ``-db`` parameter).
        :param layout: The layout to use (sets the ``-lay`` parameter).
        :param response_layout: (*Optional*) The layout to use (sets the
            ``-lay.response`` parameter).
        '''
        self.url = URLObject(url).without_auth()
        self.url = self.url.with_path(
            self.url.path or '/fmi/xml/fmresultset.xml')
        self.auth = URLObject(url).auth
        self.params = QueryDict('', mutable=True)
        self.dbparams = QueryDict('', mutable=True)
        self.dbparams.update({
            '-db': db,
            '-lay': layout,
        })
        if response_layout:
            self.dbparams['-lay.response'] = response_layout
        self.params['-max'] = '50'

    def __repr__(self):
        return '<RawManager: {0} {1} {2}>'.format(
            self.url, self.dbparams, self.params)

    def _clone(self):
        return copy.copy(self)

    def set_script(self, name, option=None):
        '''
        Sets the name of the filemaker script to use

        :param name: The name of the script to use.
        :param option: (*Optional*) Can be one of ``presort`` or ``prefind``.
        '''
        mgr = self._clone()
        key = '-script'
        if option in ('prefind', 'presort'):
            key = '{0}.{1}'.format(key, option)
        mgr.params[key] = name
        return mgr

    def set_record_id(self, recid):
        '''
        Sets the ``-recid`` parameter.

        :param recid: The record ID to set.
        '''
        mgr = self._clone()
        mgr.params['-recid'] = recid
        return mgr

    def set_modifier_id(self, modid):
        '''
        Sets the ``-modid`` parameter.

        :param modid: The modifier ID to set.
        '''
        mgr = self._clone()
        mgr.params['-modid'] = modid
        return mgr

    def set_logical_operator(self, op):
        '''
        Set the logical operator to be used for this query using the ``-op``
        parameter.

        :param op: Must be one of ``and`` or ``or``.
        '''
        mgr = self._clone()
        if op in ('and', 'or'):
            mgr.params['-lop'] = op
        return mgr

    def set_group_size(self, max):
        '''
        Set the group size to return from FileMaker using the ``-max``.

        This is defaulted to 50 when the manager is initialized.

        :param integer max: The number of records to return.
        '''
        self.params['-max'] = max
        return self

    def set_skip_records(self, skip):
        '''
        The number of records to skip when retrieving records from FileMaker
        using the ``-skip`` parameter.

        :param integer skip: The number of records to skip.
        '''
        self.params['-skip'] = skip
        return self

    def add_db_param(self, field, value, op=None):
        '''
        Adds an arbitrary parameter to the query to be performed. An optional
        operator parameter may be specified which will add an additional field
        to the parameters. e.g. ``.add_db_param('foo', 'bar')`` sets the
        parameter ``...&foo=bar&...``, ``.add_db_param('foo', 'bar', 'gt')``
        sets ``...&foo=bar&foo.op=gt&...``.

        :param field: The field to query on.
        :param value: The query value.
        :param op: (*Optional*) The operator to use for this query.
        '''
        mgr = self._clone()
        mgr.params.appendlist(field, value)
        if op:
            mgr.params.appendlist('{0}.op'.format(field), op)
        return mgr

    def add_sort_param(self, field, order='ascend', priority=0):
        '''
        Add a sort field to the query.

        :param field: The field to sort on.
        :param order: (*Optional*, defaults to ``ascend``) The direction to
            sort, one of ``ascending`` or ``descending``.
        :param priority: (*Optional*, defaults to ``0``) the order to apply
            this sort in if multiple sort fields are specified.
        '''
        mgr = self._clone()
        mgr.params['-sortfield.{0}'.format(priority)] = field
        mgr.params['-sortorder.{0}'.format(priority)] = order
        return mgr

    def find(self, **kwargs):
        '''
        Performs the -find command. This method internally calls ``_commit``
        and is not chainable.

        :param \**kwargs: Any additional fields to search on, which will be
            passed directly into the URL parameters.
        :rtype: :py:class:`filemaker.parser.FMXMLObject`
        '''
        self.params.update(kwargs)
        return self._commit('find')

    def find_all(self, **kwargs):
        '''
        Performs the -findall command to return all records. This method
        internally calls ``_commit`` and is not chainable.

        :param \**kwargs: Any additional URL parameters.
        :rtype: :py:class:`filemaker.parser.FMXMLObject`
        '''
        self.params.update(kwargs)
        return self._commit('findall')

    def edit(self, **kwargs):
        '''
        Updates a record using the ``-edit`` command. This method
        internally calls ``_commit`` and is not chainable.

        You should have either called the :py:meth:`set_record_id` and/or
        :py:meth:`set_modifier_id` methods on the manager, or passed in
        ``RECORDID`` or ``MODID`` as params.

        :param \**kwargs: Any additional parameters to pass into the URL.
        :rtype: :py:class:`filemaker.parser.FMXMLObject`
        '''
        self.params.update(kwargs)
        return self._commit('edit')

    def new(self, **kwargs):
        '''
        Creates a new record using the ``-new`` command. This method
        internally calls ``_commit`` and is not chainable.

        :param \**kwargs: Any additional parameters to pass into the URL.
        :rtype: :py:class:`filemaker.parser.FMXMLObject`
        '''
        self.params.update(kwargs)
        return self._commit('new')

    def delete(self, **kwargs):
        '''
        Deletes a record using the ``-delete`` command. This method
        internally calls ``_commit`` and is not chainable.

        You should have either called the :py:meth:`set_record_id` and/or
        :py:meth:`set_modifier_id` methods on the manager, or passed in
        ``RECORDID`` or ``MODID`` as params.

        :param \**kwargs: Any additional parameters to pass into the URL.
        :rtype: :py:class:`filemaker.parser.FMXMLObject`
        '''
        self.params.update(kwargs)
        return self._commit('delete')

    def _commit(self, action):
        if 'RECORDID' in self.params and not '-recid' in self.params:
            self.params['-recid'] = self.params['RECORDID']
            del self.params['RECORDID']
        if 'MODID' in self.params and not '-modid' in self.params:
            self.params['-modid'] = self.params['MODID']
            del self.params['MODID']
        data = '&'.join([
            self.dbparams.urlencode(),
            self.params.urlencode(),
            '-{0}'.format(action),
        ])
        try:
            resp = requests.post(self.url, auth=self.auth, data=data)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise FileMakerConnectionError(e)
        return FMXMLObject(resp.content)


class Manager(RawManager):

    '''
    A manager for use with :py:class:`filemaker.base.FileMakerModel` classes.
    Inherits from the :py:class:`RawManager`, but adds some conveniences and
    field mapping methods for use with
    :py:class:`filemaker.base.FileMakerModel` sub-classes.

    This manager can be treated as an iterator returning instances of the
    relavent :py:class:`filemaker.base.FileMakerModel` sub-class returned from
    the FileMaker server. It also supports slicing etc., although negative
    indexing is unsupported.
    '''

    def __init__(self, cls):
        '''
        :param cls: The :py:class:`filemaker.base.FileMakerModel` sub-class to
            use this manager with. It is expected that the model ``meta``
            dictionary will have a ``connection`` key to a dictionary with
            values for ``url``, ``db``, and ``layout``.
        '''
        self.cls = cls
        super(Manager, self).__init__(**self.cls._meta.get('connection'))
        self._result_cache = None
        self._fm_data = None

    def __iter__(self):
        return self.iterator()

    def iterator(self):
        if not self._result_cache:
            self._result_cache = \
                self.preprocess_resultset(self._get_fm_data().resultset)
        for result in self._result_cache:
            yield self.cls(result)

    def __len__(self):
        return len(self._get_fm_data().resultset)

    def __getitem__(self, k):
        mgr = self
        if not isinstance(k, (slice,) + six.integer_types):
            raise TypeError
        assert ((not isinstance(k, slice) and (k >= 0))
                or (isinstance(k, slice) and (k.start is None or k.start >= 0)
                    and (k.stop is None or k.stop >= 0))), \
            'Negative indexing is not supported.'
        if isinstance(k, slice):
            if k.start:
                mgr = mgr.set_skip_records(k.start)
            if k.stop:
                mgr = mgr.set_group_size(k.stop - (k.start or 0))
        return list(mgr)[k]

    def __repr__(self):
        return '<{0} query with {1} records...>'.format(
            self.cls.__name__, len(self))

    def _get_fm_data(self):
        if self._fm_data is None:
            self._fm_data = self.find()
        return self._fm_data

    def _clone(self):
        mgr = super(Manager, self)._clone()
        mgr._result_cache = None
        mgr._fm_data = None
        return mgr

    def _resolve_fm_field(self, field):
        from .fields import ModelField
        parts = field.split('__')
        fm_attr_path = []
        klass = self.cls
        resolved_field = None
        for part in parts:
            try:
                klass = resolved_field.model if resolved_field else self.cls
            except AttributeError:
                raise ValueError('Cound not resolve field: {0}'.format(field))
            resolved_field = klass._fields.get(part)
            if resolved_field is None:
                raise ValueError('Cound not resolve field: {0}'.format(field))
            path = resolved_field.fm_attr.replace('.', '::')
            if not path == '+self' and not isinstance(
                    resolved_field, ModelField):
                fm_attr_path.append(path)
        return '::'.join(fm_attr_path)

    def preprocess_resultset(self, resultset):
        '''
        This is a hook you can override on a manager to pre-process a resultset
        from FileMaker before the data is converted into model instances.

        :param resultset: The ``resultset`` attribute of the
            :py:class:`filemaker.parser.FMXMLObject` returned from FileMaker
        '''
        return resultset

    def all(self):
        '''
        A no-op returning a clone of the current manager
        '''
        return self._clone()

    def filter(self, **kwargs):
        '''
        Filter the queryset by model fields. Model field names are passed in as
        arguments rather than FileMaker fields.

        Queries spanning relationships can be made using a ``__``, and
        operators can be specified at the end of the query. e.g. Given a model:
        ::

            class Foo(FileMakerModel):
                beans = fields.IntegerField('FM_Beans')

                meta = {
                    'abstract': True,
                    ...
                }

            class Bar(FileMakerModel):
                foo = fields.ModelField('BAR_Foo', model=Foo)
                num = models.IntegerField('FM_Num'))

                meta = {
                    'connection': {...},
                    ...
                }


        To find all instances of a ``Bar`` with ``num == 4``:
        ::

            Bar.objects.filter(num=4)

        To find all instances of ``Bar`` with ``num < 4``:
        ::

            Bar.objects.filter(num__lt=4)

        To Find all instance of ``Bar`` with a ``Foo`` with ``beans == 4``:
        ::

            Bar.objects.filter(foo__beans=4)

        To Find all instance of ``Bar`` with a ``Foo`` with ``beans > 4``:
        ::

            Bar.objects.filter(foo__beans__gt=4)

        The ``filter`` method is also chainable so you can do:
        ::

            Bar.objects.filter(num=4).filter(foo__beans=4)

        :param \**kwargs: The fields and values to filter on.
        '''
        mgr = self
        for k, v in kwargs.items():
            operator = 'eq'
            for op, code in OPERATORS.items():
                if k.endswith('__{0}'.format(op)):
                    k = re.sub(r'__{0}$'.format(op), '', k)
                    operator = code
                    break
            try:
                mgr = mgr.add_db_param(
                    self._resolve_fm_field(k), v, op=operator)
            except (KeyError, ValueError):
                raise ValueError('Invalid filter argument: {0}'.format(k))
        return mgr

    def get(self, **kwargs):
        '''
        Returns the first item found by filtering the queryset by ``**kwargs``.
        Will raise the ``DoesNotExist`` exception on the managers model class
        if no items are found, however, unlike the Django ORM, will silently
        return the first result if multiple results are found.

        :param \**kwargs: Field and value queries to be passed to
            :py:meth:`filter`
        '''

        try:
            return self.filter(**kwargs)[0]
        except IndexError:
            raise self.cls.DoesNotExist('Could not find item in FileMaker')

    def order_by(self, *args):
        '''
        Add an ordering to the queryset with respect to a field.

        If the field name is prepended by a ``-`` that field will be sorted in
        reverse. Multiple fields can be specified.

        This method is also chainable so you can do, e.g.:
        ::

            Foo.objects.filter(foo='bar').order_by('qux').filter(baz=1)

        :param \*args: The field names to order by.
        '''
        mgr = self._clone()
        for key in list(mgr.params.keys()):
            if key.startswith('-sortfield') or key.startswith('-sortorder'):
                mgr.params.pop(key)
        i = 0
        for arg in args:
            if arg.startswith('-'):
                mgr = mgr.add_sort_param(
                    mgr._resolve_fm_field(arg[1:]), 'descend', i)
            else:
                mgr = mgr.add_sort_param(
                    mgr._resolve_fm_field(arg), 'ascend', i)
            i += 1
        return mgr

    def count(self):
        '''
        Returns the number of results returned from FileMaker for this query.
        '''
        return len(self)
