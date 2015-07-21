from django.dispatch import Signal

pre_create = Signal(
    providing_args=['request', 'data'],
    use_caching=True
)

post_create = Signal(
    providing_args=[
        'request',
        'serializer',
        'instance'
    ],
    use_caching=True
)

pre_update = Signal(
    providing_args=[
        'request',
        'serializer',
        'instance'
    ],
    use_caching=True
)

post_update = Signal(
    providing_args=[
        'request',
        'serializer',
        'instance',
        'pre_data'
    ],
    use_caching=True
)

pre_delete = Signal(
    providing_args=['request', 'instance'],
    use_caching=True
)

post_delete = Signal(
    providing_args=[
        'request',
        'instance',
        'pre_data'
    ],
    use_caching=True
)
