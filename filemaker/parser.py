# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
from collections import deque

from django.utils.encoding import force_text
from lxml import etree

from .exceptions import FileMakerServerError


class FMDocument(dict):
    '''
    A dictionary subclass for containing a FileMaker result whose keys can
    be accessed as attributes.
    '''

    def __getattr__(self, name):
        return self.get(name)

    def __setattr__(self, name, value):
        self[name] = value


class XMLNode(object):

    def __init__(self, name, attrs):
        self.name = name.replace(
            '{http://www.filemaker.com/xml/fmresultset}', '')
        self.attrs = attrs
        self.text = ''
        self.children = []

    def __getitem__(self, key):
        return self.attrs.get(key)

    def __setitem__(self, key, value):
        self.attrs[key] = value

    def __delitem__(self, key):
        del self.attrs[key]

    def add_child(self, element):
        self.children.append(element)

    def get_data(self):
        return self.text.strip() if hasattr(self.text, 'strip') else ''

    def get_elements(self, name=''):
        if not name:
            return self.children
        elements = []
        for element in self.children:
            if element.name == name:
                elements.append(element)
        return elements

    def get_element(self, name=''):
        if not name:
            return self.children[0]
        for element in self.children:
            if element.name == name:
                return element


class FMXMLTarget(object):

    def __init__(self):
        # It shouldn't make much difference unless you have massive
        # nested elements in a layout, but a deque should be faster than
        # a list here
        self.stack = deque()
        self.root = None

    def start(self, name, attrs):
        element = XMLNode(name, attrs)
        if self.stack:
            parent = self.stack[-1]
            parent.add_child(element)
        else:
            self.root = element
        self.stack.append(element)

    def end(self, name):
        self.stack.pop()

    def data(self, content):
        content = force_text(content)
        element = self.stack[-1]
        element.text += content

    def comment(self, text):
        pass

    def close(self):
        root = self.root
        self.stack = deque()
        self.root = None
        return root


class FMXMLObject(object):
    '''
    A python container container for results returned from a FileMaker request.

    The following attributes are provided:

    .. py:attribute:: data

        Contains the raw XML data returned from filemaker.

    .. py:attribute:: errorcode

        Contains the ``errorcode`` returned from FileMaker. Note that if this
        value is not zero when the data is parsed at instantiation, then a
        :py:exc:`filemaker.exceptions.FileMakerServerError` will be raised.

    .. py:attribute:: product

        A dictionary containing the FileMaker product details returned from
        the server.

    .. py:attribute:: database

        A dictionary containing the FileMaker database information returned
        from the server.

    .. py:attribute:: metadata

        A dictionary containing any metadata returned by the FileMaker server.

    .. py:attribute:: resultset

        A list containing any results returned from the FileMaker server as
        :py:class:`FMDocument` instances.

    .. py:attribute:: field_names

        A list of field names returned by the server.

    .. py:attribute:: target

        The target class used by lxml to parse the XML response from the
        server. By default this is an instance of :py:class:`FMXMLTarget`, but
        this can be overridden in subclasses.
    '''

    target = FMXMLTarget()

    def __init__(self, data):
        self.data = data
        self.errorcode = -1
        self.product = {}
        self.database = {}
        self.metadata = {}
        self.resultset = []
        self.field_names = []
        self._parse_resultset()

    def __getitem__(self, key):
        return self.resultset[key]

    def __len__(self):
        return len(self.resultset)

    def _parse_xml(self):
        parser = etree.XMLParser(target=self.target)
        xml_obj = etree.XML(self.data, parser)
        try:
            if xml_obj.get_elements('ERRORCODE'):
                self.errorcode = \
                    int(xml_obj.get_elements('ERRORCODE')[0].get_data())
            else:
                self.errorcode = int(xml_obj.get_elements('error')[0]['code'])
        except (KeyError, IndexError, TypeError, ValueError):
            raise FileMakerServerError(954)

        if self.errorcode == 401:
            # Object not found on filemaker so return None which we pick
            # up later as no objects having been found
            return
        if not self.errorcode == 0:
            raise FileMakerServerError(self.errorcode)

        return xml_obj

    def _parse_resultset(self):
        data = self._parse_xml()
        if data is None:
            self.resultset = []
            return
        self.product = data.get_element('product').attrs
        self.database = data.get_element('datasource').attrs
        definitions = data.get_element(
            'metadata').get_elements('field-definition')
        for definition in definitions:
            self.metadata[definition['name']] = definition.attrs
            self.field_names.append(definition['name'])
        results = data.get_element('resultset')
        for result in results.get_elements('record'):
            record = FMDocument()
            for column in result.get_elements('field'):
                field_name = column['name']
                column_data = None
                if column.get_element('data'):
                    column_data = column.get_element('data').get_data()
                if '::' in field_name:
                    sub_field, sub_name = field_name.split('::', 1)
                    if not sub_field in record:
                        record[sub_field] = FMDocument()
                    record[sub_field][sub_name] = column_data
                else:
                    record[field_name] = column_data
            record['RECORDID'] = int(result['record-id'])
            record['MODID'] = int(result['mod-id'])

            for sub_node in result.get_elements('relatedset'):
                sub_node_name = sub_node['table']
                if sub_node['count'] > 0:  # and not sub_node_name in record:
                    record[sub_node_name] = []
                for sub_result in sub_node.get_elements('record'):
                    sub_record = FMDocument()
                    for sub_column in sub_result.get_elements('field'):
                        field_name = re.sub(
                            r'^{0}::'.format(sub_node_name), '',
                            sub_column['name'])
                        if not sub_column.get_element('data'):
                            continue
                        column_data = sub_column.get_element('data').get_data()
                        if '::' in field_name:
                            sub_field, sub_name = field_name.split('::', 1)
                            if not sub_field in sub_record:
                                sub_record[sub_field] = FMDocument()
                            sub_record[sub_field][sub_name] = column_data
                        else:
                            sub_record[field_name] = column_data
                    sub_record['RECORDID'] = int(sub_result['record-id'])
                    sub_record['MODID'] = int(sub_result['mod-id'])
                    record[sub_node_name].append(sub_record)

            self.resultset.append(record)
