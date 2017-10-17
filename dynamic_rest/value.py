from uuid import UUID
from datetime import datetime, date


class BaseValue(object):

    @property
    def field(self):
        return self._field

    @property
    def instance(self):
        return self._instance

    def render(self, format=None):
        if hasattr(self._field, 'render'):
            return self._field.render(self, format)
        return self


class Value(object):
    __classes = {}

    def __new__(cls, *args, **kwargs):
        value = args[0] if args else None
        if value is None:
            return None

        field = kwargs.get('field', None)
        instance = kwargs.get('instance', None)

        if isinstance(value, (UUID, datetime, date)):
            value = str(value)

        value_class = value.__class__
        new_class_name = 'x%s' % value_class.__name__
        if not cls.__classes.get(new_class_name):
            try:
                cls.__classes[new_class_name] = type(
                    new_class_name,
                    (
                        BaseValue,
                        value_class
                    ),
                    {}
                )
            except:
                # some primitives cannot be subclasses (bool/None)
                return value

        new_class = cls.__classes[new_class_name]
        # create instance
        new_value = new_class.__new__(
            new_class,
            value
        )
        # set meta properties
        new_value._value = value
        new_value._field = field
        new_value._instance = instance
        # initialize
        new_class.__init__(new_value, value)
        # transfer object properties
        if hasattr(value, '__dict__'):
            for k, v in value.__dict__.items():
                if not k.startswith('_'):
                    try:
                        setattr(new_value, k, v)
                    except:
                        pass
        return new_value
