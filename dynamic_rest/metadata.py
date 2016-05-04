"""This module contains custom DRF metadata classes."""
from collections import OrderedDict

from django.utils.encoding import force_text
from rest_framework.fields import empty
from rest_framework.metadata import SimpleMetadata
from rest_framework.serializers import ListSerializer, ModelSerializer

from dynamic_rest.fields import DynamicRelationField


class DynamicMetadata(SimpleMetadata):
    """A subclass of SimpleMetadata.

    Adds `properties` and `features` to the metdata.
    """

    def determine_actions(self, request, view):
        """Prevent displaying action-specific details."""
        return None

    def determine_metadata(self, request, view):
        """Adds `properties` and `features` to the metadata response."""
        metadata = super(
            DynamicMetadata,
            self).determine_metadata(
            request,
            view)
        metadata['features'] = getattr(view, 'features', [])
        if hasattr(view, 'get_serializer'):
            serializer = view.get_serializer(dynamic=False)
            if hasattr(serializer, 'get_name'):
                metadata['resource_name'] = serializer.get_name()
            if hasattr(serializer, 'get_plural_name'):
                metadata['resource_name_plural'] = serializer.get_plural_name()
        metadata['properties'] = self.get_serializer_info(serializer)
        return metadata

    def get_field_info(self, field):
        """Adds `related_to` and `nullable` to the metadata response."""
        field_info = OrderedDict()
        for attr in ('required', 'read_only', 'default', 'label'):
            field_info[attr] = getattr(field, attr)
        if field_info['default'] is empty:
            field_info['default'] = None
        if hasattr(field, 'immutable'):
            field_info['immutable'] = field.immutable
        field_info['nullable'] = field.allow_null
        if hasattr(field, 'choices'):
            field_info['choices'] = [
                {
                    'value': choice_value,
                    'display_name': force_text(choice_name, strings_only=True)
                }
                for choice_value, choice_name in field.choices.items()
            ]
        many = False
        if isinstance(field, DynamicRelationField):
            field = field.serializer
        if isinstance(field, ListSerializer):
            field = field.child
            many = True
        if isinstance(field, ModelSerializer):
            type = 'many' if many else 'one'
            field_info['related_to'] = field.get_plural_name()
        else:
            type = self.label_lookup[field]

        field_info['type'] = type
        return field_info
