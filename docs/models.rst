FileMakerModels
===============

.. py:module:: filemaker.base
.. py:class:: FileMakerModel

    :py:class:`FileMakerModel` objects provide a way to map FileMaker layouts to
    Django models, providing validation, and query methods.
    
    They provide a simple field based API similar to the Django model interface.

    .. py:method:: to_dict
        
        The :py:meth:`to_dict` method serializes the FileMaker model hierarchy
        represented by this model instance to a dictionary structure.

    .. py:method:: to_django

        The :py:meth:`to_django` converts this FileMaker model instance into
        an instance of the Django model specified by the ``model`` value of the
        classes :py:attr:`meta` dictionary.

    .. py:attribute:: meta

        the :py:attr:`meta` dictionary on a FileMaker model class is similar to
        the ``Meta`` class on a Django model. See :ref:`the-meta-dictionary`,
        below, for a full list of options.
    
    
.. _the-meta-dictionary:

The ``meta`` dictionary
-----------------------
The ``meta`` dictionary on a model is equivalent to the ``Meta`` class on a
Django model. The ``meta`` dictionary may contain any of the following keys.

``connection``:
    For the base model to be queried from a FileMaker layout, this
    should contain a ``connection`` dictionary with ``url``, ``db``, and 
    ``layout`` fields (and an optional ``response_layout`` field).

``model``:
    The Django model class that this :py:class:`FileMakerModel` maps to.

``pk_name``:
    The field name on the :py:class:`FileMakerModel` that maps to the
    Django model ``pk`` field. By default this is ``id`` or ``pk``
    whichever field is present.

``django_pk_name``:
    The django ``pk`` field name. This should almost never need to be
    changed unless you're doing (*very*) weird things with your Django models.

``django_field_map``:
    An optional dictionary mapping fields on the :py:class:`FileMakerModel`
    to fields on the Django model. By default the names are mapped
    one-to-one between the two.

``abstract``:
    If this is set to ``True`` it denotes that the model is a subsection of
    the layout fields, or a list-field on the layout, i.e. this model
    doesn't specify a ``connection`` but is connected to one that does by
    one or more :py:class:`filemaker.fields.ModelField` or
    :py:class:`filemaker.fields.ModelListField` instances.

``to_many_action``:
    If this is set to ``clear``, the default, then when converting
    :py:class:`FileMakerModel` instances to Django instances, existing
    many-to-many relations will be cleared before being re-added.

``ordering``:
    Does what it says on the tin. ``id`` by default.

``default_manager``:
    The default manager class to use for the model. This is
    :py:class:`filemaker.manager.Manager` by default.

``related`` and ``many_related``:
    These contain reverse entries for 
    :py:class:`filemaker.fields.ModelField` or 
    :py:class:`filemaker.fields.ModelListField` instances on other models
    pointing back to the current model.


Declaring fields
----------------

Fields are declared exactly as with Django models, the exception being that
FileMaker fields are used. Field names should either have the same name as
their Django model counterparts, unless you are using the ``django_field_map``
attribute of the ``meta`` dictionary. For example, we could write a
FileMakerModel mapping to the Django FlatPage model as the following:

::

    from django.contrib.flatpages.models import FlatPage
    from django.contrib.sites.models import Site
    from filemaker import FileMakerModel, fields

    class FileMakerSite(FileMakerModel):
        d = fields.CharField('FM_domain')
        n = fields.CharField('FM_name')

        meta = {
            'model': Site,
            'abstract': True,  
            'django_field_map': {
                'd': 'domain',
                'n': 'name',
            },
        }

    class FileMakerFlatPage(FileMakerModel):

        url = fields.CharField('FM_url')
        title = fields.CharField('FM_title')
        content = fields.CharField('FM_content', default='')
        enable_comments = fields.BooleanField('FM_enable_comments')
        template_name = fields.CharField('FM_template_name')
        registration_required = fields.BooleanField('FM_registration_required')
        sites = fields.ModelListField('SITES', model=FileMakerSite)

        meta = {
            'connection': {
                'url': 'http://user:pass@192.168.0.2',
                'db': 'main',
                'layout': 'flatpages',
            },
            'model': FlatPage,
        }


Here we have used different field names on the ``FileMakerSite`` model, and 
re-mapped them to the Django ``Site``. We have here assumed a FileMaker layout
structure something like:

::

    - FM_url: The URL for the flatpage.
      FM_title: The title of the flatpage.
      FM_content: The content for the flatpage.
      FM_enable_comments: ...
      FM_template_name: ...
      FM_registration_required: ...
      SITES:
          - FM_domain: The domain of the site.
            FM_name: The name of the site
          - FM_domain: ...
            FM_name: ...
          - ...
    - FM_url: ...
      FM_title: ...
      ...
    - ...

For a full list of field type see the :ref:`field-reference`.
