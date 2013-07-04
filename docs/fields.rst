Fields
======

Fields provide the data coersion and validation when pulling data from
FileMaker. All fields should inherit from the :py:class:`BaseFileMakerField`.

.. py:class:: filemaker.fields.BaseFileMakerField(fm_attr=None, *args, **kwargs)
    
    This is the base implementation of a field. It should not be used directly,
    but should be inherited by every FileMaker field class.
        
    :param fm_attr: The attribute on the FileMaker layout that this field
        relates to. If none is given then the field name used on the
        FileMakerModel will be substituted.

    :param \**kwargs: And keyword arguments are attached as attributes to the
        field instance, or used to override base attributes.

    Aside from the ``fm_attr`` following attributes are defined by the base 
    field:

    .. py:attribute:: null

        Determines whether this field is allowed to take a ``None`` value.

    .. py:attribute:: null_values

        The values that will be treated as ``null``, by default the empty
        string ``''`` and ``None``.

    .. py:attribute:: default

        The default value to use for this field if none is given.

    .. py:attribute:: validators

        A list of functions that take a single argument that will be used to
        validate the field. Compatible with Django's field validators.

    .. py:attribute:: min

        Specifies the minimum value this field can take.

    .. py:attribute:: max

        Specifies the maximum value this field can take.

    The current value of a FileMaker field is available using the ``value``
    attribute.


.. _field-reference:

FileMakerField reference
------------------------

The following fields are provided by Django filemaker.

.. automodule:: filemaker.fields
    :members:
