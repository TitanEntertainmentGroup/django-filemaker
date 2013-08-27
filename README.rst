django-filemaker
================

Pythonic FileMaker® access and FileMaker layout to Django model mapping.

.. image:: https://badge.fury.io/py/django-filemaker.png
    :target: http://badge.fury.io/py/django-filemaker

.. image:: https://travis-ci.org/TitanEntertainmentGroup/django-filemaker.png?branch=master
    :target: https://travis-ci.org/TitanEntertainmentGroup/django-filemaker

.. image:: https://coveralls.io/repos/TitanEntertainmentGroup/django-filemaker/badge.png?branch=master
    :target: https://coveralls.io/r/TitanEntertainmentGroup/django-filemaker?branch=master

.. image:: https://pypip.in/d/django-filemaker/badge.png
        :target: https://crate.io/packages/django-filemaker?version=latest

Quickstart
----------

Create a ``FileMakerModel``:
::
    
    from django.contrib.flatpages.models import FlatPage
    from django.contrib.sites.models import Site
    from filemaker import fields, FileMakerModel


    class FileMakerFlatPage(FileMakerModel):

        # The first argument to a FileMaker field should be the field name for
        # that item on the FileMaker layout
        pk = fields.IntegerField('zpkFlatpageID')
        url = fields.CharField('Url_FileMaker_Field')
        title = fields.CharField('Title_FileMaker_Field')
        content = fields.CharField('Content_FileMaker_Field')
        # You can pass in a default value to any field
        template_name = fields.CharField(
            'Template_Name_Field', default='flatpages/default.html')
        registration_required = fields.BooleanField(
            'Registration_Required_Field', default=False)
        sites = fields.ModelListField('SITES', model=FileMakerSite)

        meta = {
            'connection': {
                'url': 'http://user:password@example.com/',
                'db': 'Db_Name',
                'layout': 'Layout_Name',
            },
            'model': FlatPage,
            'pk_name': 'pk',
        }

    class FileMakerSite(FileMakerModel):
        # On related fields we specify the relative field to the field name
        # specified on the calling model (FileMakerFlatPage), unless the
        # calling model uses the special '+self' value which passes the layout
        # of that model to the sub model
        domain = fields.CharField('Domain_field')
        name = fields.CharField('Name_Field')

        meta = {
            'model': Site,
            # abstract here means it is a child of an actual FileMaker layout
            'abstract': True,  
        }


Query FileMaker for instances of your model, and convert them to django
instances using the ``to_django`` method:
::
    >>> # The Django style methods will convert field names
    >>> FlatPage.objects.count() == 0
    True
    >>> fm_page = FileMakerFlatPage.objects.get(pk=1)
    >>> fm_page.to_django()
    <FlatPage: pk=1>
    >>> FlatPage.objects.count() == 1
    True


You can also use the FileMaker style manager methods to query:
::

    >>> FileMakerFlatPage.objects.find(zpkFlatpageID=1)
    <FMXMLObject...>

Documentation
-------------

Full documentation is available on `ReadTheDocs
<https://django-filemaker.readthedocs.org/en/latest/>`_
