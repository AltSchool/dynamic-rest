from collections import OrderedDict
from django.utils.encoding import force_text
from dynamic_rest.fields import DynamicRelationField
from rest_framework.metadata import SimpleMetadata
from rest_framework.serializers import ListSerializer, ModelSerializer

class DynamicMetadata(SimpleMetadata):
  def determine_actions(self, request, view):
    """Prevents displaying action-specific details.
    """
    return None

  def determine_metadata(self, request, view):
    """Adds `properties` and `features` to the metadata response.
    """
    metadata = super(DynamicMetadata, self).determine_metadata(request, view)
    metadata['features'] = getattr(view, 'features', [])
    if hasattr(view, 'get_serializer'):
      serializer = view.get_serializer(dynamic=False)
    metadata['properties'] = self.get_serializer_info(serializer)
    return metadata

  def get_field_info(self, field):
    """Adds `related_to` and `nullable` to the metadata response.
    """
    field_info = OrderedDict()
    for attr in ('required', 'read_only', 'default', 'label'):
      field_info[attr] = getattr(field, attr)
    field_info['nullable'] = field.allow_null
    if hasattr(field, 'choices'):
      field_info['choices'] = [
        {
          'value': choice_value,
          'display_name': force_text(choice_name, strings_only=True)
        }
      ]
    many = False
    if isinstance(field, DynamicRelationField):
      field = field.serializer
    if isinstance(field, ListSerializer):
      field = field.child
      many = True
    if isinstance(field, ModelSerializer):
      type = 'many' if many else 'one'
      field_info['related_to'] = field.get_name()
    else:
      type = self.label_lookup[field]

    field_info['type'] = type
    return field_info
