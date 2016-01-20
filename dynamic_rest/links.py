"""This module contains utilities to support API links."""
from django.utils import six


def merge_link_object(serializer, data, instance):
    """Add a 'links' attribute to the data that maps field names to URLs.

    NOTE: This is the format that Ember Data supports, but alternative
          implementations are possible to support other formats.
    """

    link_object = {}

    if not getattr(instance, 'pk', None):
        # If instance doesn't have a `pk` field, we'll assume it doesn't
        # have a canonical resource URL to hang a link off of.
        # This generally only affectes Ephemeral Objects.
        return data

    link_fields = serializer.get_link_fields()
    for name, field in six.iteritems(link_fields):
        # For included fields, omit link if there's no data.
        if name in data and not data[name]:
            continue

        # Default to DREST-generated relation endpoints.
        link = getattr(field, 'link', "/%s/%s/%s/" % (
            serializer.get_plural_name(),
            instance.pk,
            name
        ))
        if callable(link):
            link = link(name, field, data, instance)

        link_object[name] = link

    if link_object:
        data['links'] = link_object
    return data
