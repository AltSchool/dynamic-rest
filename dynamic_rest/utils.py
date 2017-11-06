from django.utils.six import string_types

FALSEY_STRINGS = (
    '0',
    'false',
    '',
)


def is_truthy(x):
    if isinstance(x, string_types):
        return x.lower() not in FALSEY_STRINGS
    return bool(x)
