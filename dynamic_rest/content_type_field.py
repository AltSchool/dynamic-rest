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

    def id_only(self):
        if self.parent and self.field_name:
            parent_request_fields = getattr(
                self.parent,
                'request_fields',
                {}
            )
            return parent_request_fields.get(self.field_name)

    def to_representation(self, instance):

        try:
            # Determine resource type
            resource_key = instance._meta.db_table

            # Find serializer for that resource type
            serializer_class = DynamicRouter.get_canonical_serializer(
                resource_key
            )

            # TODO: Add support for `id_only()` here.
            if self.id_only():
                return {
                    'type': serializer_class().get_plural_name(),
                    'id': instance.pk
                }

            # TODO: In theory, it is possible to inject require_fields here
            #       and support field inclusion/exclusion...
            return serializer_class(context=self.context).to_representation(
                instance
            )
        except:
            traceback.print_exc()
            return None
