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

    .. py:method:: coerce(self, value)

        Takes a value and either returns the value coerced into the required
        type for the field or raises a
        :py:exc:`filemaker.exceptions.FileMakerValidationError` with an
        explanatory message. This method is called internally by the private
        ``_coerce`` method during validation.

    .. py:method:: to_django(self, \*args, \**kwargs)

        Does any processing on the fields' value required before it can be
        passed to a Django model. By default this just returns ``self.value``.

    The current value of a FileMaker field is available using the ``value``
    attribute.


.. _field-reference:

FileMakerField reference
------------------------

The following fields are provided by Django filemaker.

.. automodule:: filemaker.fields
    :members:


Creating custom fields
----------------------

.. py:currentmodule:: filemaker.fields

If your custom field only requires a simple validation check, then it is
easiest to override the validators list for a field by passing in a new list of
validators.

If you require more control over your field, you can subclass
:py:class:`BaseFileMakerField`, or the field class that most closely resembles
your desired type. The two methods that you will likely wish to overwrite are
the :py:meth:`BaseFileMakerField.coerce` method, and the
:py:meth:`BaseFileMakerField.to_django` method.

:py:meth:`BaseFileMakerField.coerce` is called by the private 
``_coerce`` method during validation. It should take a single ``value`` 
parameter and either return an instance of the required type, or raise a
:py:exc:`filemake.exceptions.FileMakerValidationError` with an explanation of
why the value could not be coerced.

:py:meth:`BaseFileMakerField.to_django` does any post processing on the 
field required to render it suitable for passing into a Django field. By 
default this method just returns the field instances' current value.

As an example, if we wanted to have a field that took a string and added "from
FileMaker" to the end of it's value we could do:
::
    
    from filemaker.fields import CharField

    class FromFileMakerCharField(CharField):
        
        def coerce(self, value):
            text = super(FromFileMakerCharField, self).coerce(value)
            return '{0} from FileMaker'.format(text)


If we wanted to remove the extra string before passing the value into a Django
model, we could add a :py:meth:`BaseFileMakerField.to_django` method, 
like so:
::
    
    import re

    from filemaker.fields import CharField

    class FromFileMakerCharField(CharField):
        
        def coerce(self, value):
            text = super(FromFileMakerCharField, self).coerce(value)
            return '{0} from FileMaker'.format(text)

        def to_django(self):
            return re.sub(r' from FileMaker$', '', self.value)
