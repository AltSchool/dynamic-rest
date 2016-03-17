import traceback

from dynamic_rest.routers import DynamicRouter
from dynamic_rest.fields import DynamicField


class DynamicContentTypeField(DynamicField):

    def __init__(
        self,
        object_field=None,
        type_field=None,
        id_field=None,
        *args, **kwargs
    ):
        # NOTE: object_field should be same as `source`, except `source`
        #       isn't reliably available until this field is bound().
        if not object_field:
            raise Exception(
                'DynamicContentTypeField requires `object_field` kwarg'
            )

        # Infer type field and id field from object_field if not explicitly set
        type_field = type_field or object_field + '_type'
        id_field = id_field or object_field + '_id'

        # Inject `requires` so required fields get prefetched properly.
        # TODO: It seems like we should be able to require the type and
        #       id fields, but that seems to conflict with some internal
        #       Django magic. Disabling `.only()` by requiring '*' seem
        #       to work more reliably...
        kwargs['requires'] = kwargs.pop('requires', []) + [
            object_field + '.*',
            '*'
        ]
        kwargs['read_only'] = True
        super(DynamicContentTypeField, self).__init__(*args, **kwargs)

    def to_representation(self, instance):
        try:
            # Fetch related object, determine its type
            resource_key = instance._meta.db_table

            # Find serializer for that resource type
            serializer_class = DynamicRouter.get_canonical_serializer(
                resource_key
            )

            # TODO: In theory, it is possible to inject require_fields here
            #       and support field inclusion/exclusion...
            return serializer_class(context=self.context).to_representation(
                instance
            )
        except:
            traceback.print_exc()
            return None
