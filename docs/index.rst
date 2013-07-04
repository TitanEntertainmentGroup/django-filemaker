.. django-filemaker documentation master file, created by
   sphinx-quickstart on Fri Jun 28 12:48:27 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

django-filemaker documentation
==============================

Pythonic FileMaker® access and FileMaker layout to Django model mapping.

``django-filemaker`` provides a framework for basic interaction with a
FileMaker® database via its web XML publisher interface, and a simple model
style formulation to retrieve objects from FileMaker® and map them into Django
model instances.


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


You can also use the FileMaker style manager methods to query FileMaker, these
return the result as a :py:class:`filemaker.parser.FMXMLObject`:

::

    >>> FileMakerFlatPage.objects.find(zpkFlatpageID=1)
    <FMXMLObject: ...>
    

Contents
========

.. toctree::
   :maxdepth: 2

   managers
   models
   fields
   exceptions

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

