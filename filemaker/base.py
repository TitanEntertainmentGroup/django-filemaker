# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from copy import deepcopy

from django.db.models import FieldDoesNotExist, ForeignKey, ManyToManyField
from django.utils import six

from .exceptions import FileMakerObjectDoesNotExist

try:
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


class ManagerDescriptor(object):

    def __init__(self, manager):
        self.manager = manager

    def __get__(self, instance, type=None):
        if instance is not None:
            raise AttributeError(
                'Manager isn\'t accessible via {0} instances'.format(
                    type.__name__))
        return self.manager(type)


class BaseFileMakerModel(type):

    def __new__(cls, name, bases, attrs):
        from .fields import BaseFileMakerField
        from .manager import Manager
        super_new = super(BaseFileMakerModel, cls).__new__

        if name == 'NewBase' and attrs == {}:
            return super_new(cls, name, bases, attrs)

        meta_override = attrs.pop('meta', {})
        fields = []
        new_attrs = []
        new_attrs.append((
            'DoesNotExist',
            type(str('DoesNotExist'), (FileMakerObjectDoesNotExist,), {})
        ))
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, BaseFileMakerField):
                attr_value.name = attr_name
                if attr_value.fm_attr is None:
                    attr_value.fm_attr = attr_name
                field = deepcopy(attr_value)
                fields.append((attr_name, field))
            else:
                new_attrs.append((attr_name, attr_value))
        fields = dict(fields)
        new_attrs.append(('_fields', fields))
        meta = {
            'connection': None,
            'pk_name':
            'id' if 'id' in fields else ('pk' if 'pk' in fields else None),
            'django_pk_name': 'pk',
            'django_model': None,
            'django_field_map': None,
            'abstract': False,
            'to_many_action': 'clear',
            'ordering': 'id' if 'id' in fields else None,
            'default_manager': Manager,
            'related': [],
            'many_related': [],
        }
        if isinstance(meta_override, dict):
            meta.update(meta_override)
        new_attrs.append(('_meta', meta))
        new_class = super_new(cls, name, bases, dict(new_attrs))
        new_class._attach_manager()
        new_class._process_fields()
        return new_class

    def _attach_manager(cls):

        from .manager import Manager

        if not cls._meta['abstract'] and cls._meta['connection']:
            setattr(cls, '_base_manager', ManagerDescriptor(Manager))
            setattr(
                cls,
                '_default_manager',
                ManagerDescriptor(cls._meta['default_manager'])
            )
            if not isinstance(getattr(
                    cls, 'objects', None), cls._meta['default_manager']):
                setattr(
                    cls,
                    'objects',
                    ManagerDescriptor(cls._meta['default_manager'])
                )

    def _process_fields(cls):
        for field in cls._fields.values():
            if hasattr(field, 'contribute_to_class'):
                field.contribute_to_class(cls)


@total_ordering
class FileMakerModel(six.with_metaclass(BaseFileMakerModel)):

    def __init__(self, fm_obj=None, **kwargs):
        self._fields = deepcopy(self._fields)
        self._meta = deepcopy(self._meta)

        def make_prop(field_name):

            def getter(self):
                return self._fields[field_name].value

            def setter(self, value):
                self._fields[field_name].value = value

            return property(getter, setter)

        for field_name, field in self._fields.items():
            field._value = field.default
            setattr(self.__class__, field_name, make_prop(field_name))
        if fm_obj is not None:
            for field_name, field in self._fields.items():
                value = deep_getattr(fm_obj, field.fm_attr)
                field.value = value
        else:
            for name, value in kwargs.items():
                setattr(self, name, value)
        self._fm_obj = fm_obj
        super(FileMakerModel, self).__init__()

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        for field in self._fields:
            if not field in other._fields \
                    or not other._fields[field] == self._fields[field]:
                return False
        return True

    def __lt__(self, other):
        if not isinstance(other, self.__class__):
            raise TypeError('Cannot compare {0} to {1}'
                            .format(self.__class__, other.__class__))
        ordering = self._meta['ordering']
        if ordering is None:
            raise ValueError('You must specify a field to order by in meta')
        if ordering.startswith('-'):
            ordering = ordering[1:]
            return getattr(self, ordering) > getattr(other, ordering)
        return getattr(self, ordering) < getattr(other, ordering)

    def get_django_instance(self):
        if self._meta['pk_name']:
            pk = getattr(self, self._meta['pk_name'], None)
        else:
            pk = None
        manager = self._meta['model']._default_manager
        lookup = {self._meta['django_pk_name']: pk}
        if pk is not None and manager.filter(**lookup).exists():
            obj = manager.get(**lookup)
        elif pk is not None:
            obj = self._meta['model'](**lookup)
        else:
            obj = self._meta['model']()
        return obj

    def to_django(self, *args, **kwargs):
        from .fields import ModelField, ModelListField
        if self._meta.get('model', None) is None:
            return
        obj = self.get_django_instance()
        to_one_rels = []
        to_many_rels = []
        if self._meta['django_field_map']:
            for field, dj_field in self._meta['django_field_map']:
                if isinstance(self._fields[field], ModelListField):
                    to_many_rels.append((dj_field, self._fields[field]))
                elif isinstance(self._fields[field], ModelField):
                    to_one_rels.append((dj_field, self._fields[field]))
                else:
                    setattr(obj, dj_field,
                            self._fields[field].to_django())
        else:
            for field, instance in self._fields.items():
                if isinstance(instance, ModelListField):
                    to_many_rels.append((field, instance))
                elif isinstance(instance, ModelField):
                    to_one_rels.append((field, instance))
                else:
                    setattr(obj, field, instance.to_django())
        for field_name, field in to_one_rels:
            instance = field.to_django()
            setattr(obj, field_name, instance)
        if kwargs.get('save', True):
            obj.save()
        for field_name, field in to_many_rels:
            instances = field.to_django(save=False)
            try:
                obj._meta.get_field(field_name)
            except FieldDoesNotExist:
                # If we're here then this is a reverse relationship
                rel_field = None
                for model_field in field.model._meta['model']._meta.fields:
                    if isinstance(model_field, (ForeignKey, ManyToManyField)) \
                            and model_field.rel.to == obj.__class__:
                        rel_field = model_field.name
                        break
                if rel_field is not None:
                    if self._meta['to_many_action'] == 'clear':
                        field.model._meta['model']._default_manager.filter(
                            **{rel_field: obj}).delete()
                    [setattr(instance, rel_field, obj)
                        for instance in instances]
                [instance.save() for instance in instances]
            else:
                # This looks like a m2m on the obj
                manager = getattr(obj, field_name)
                if self._meta['to_many_action'] == 'clear':
                    manager.clear()
                [instance.save() for instance in instances]
                manager.add(*instances)
        return obj

    def to_dict(self, *args, **kwargs):
        from .fields import ModelField, ModelListField
        field_dict = {}
        for field, instance in self._fields.items():
            if isinstance(instance, ModelListField):
                field_dict[field] = \
                    [i.to_dict() for i in instance.value]
            elif isinstance(instance, ModelField):
                field_dict[field] = instance.value.to_dict()
            else:
                field_dict[field] = instance.value
        return field_dict


def deep_getattr(obj, attr):
    value = obj
    if not hasattr(attr, 'strip') or not attr.strip():
        raise ValueError('You must specify an attribute name')
    if attr.strip() == '+self':
        return value
    for sub_attr in attr.split('.'):
        try:
            value = getattr(value, sub_attr)
        except AttributeError:
            return None
    return value
