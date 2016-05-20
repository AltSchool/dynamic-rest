"""This module contains utilities to support API links."""
from django.utils import six

from dynamic_rest.conf import settings
from dynamic_rest.routers import DynamicRouter


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

        link = getattr(field, 'link', None)
        if link is None:
            base_url = ''
            if settings.ENABLE_HOST_RELATIVE_LINKS:
                # if the resource isn't registered, this will default back to
                # using resource-relative urls for links.
                base_url = DynamicRouter.get_canonical_path(
                    serializer.get_resource_key(),
                    instance.pk
                ) or ''
            link = '%s%s/' % (base_url, name)
        # Default to DREST-generated relation endpoints.
        elif callable(link):
            link = link(name, field, data, instance)

        link_object[name] = link

    if link_object:
        data['links'] = link_object
    return data
