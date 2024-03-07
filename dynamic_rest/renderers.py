"""This module contains custom renderer classes."""
from rest_framework.renderers import BrowsableAPIRenderer


class DynamicBrowsableAPIRenderer(BrowsableAPIRenderer):
    """Renderer class that adds directory support to the Browsable API."""

    template = "dynamic_rest/api.html"

    def get_context(self, data, accepted_media_type, renderer_context):
        """Return the context."""
        from dynamic_rest.routers import (  # pylint: disable=import-outside-toplevel
            get_directory,
        )

        context = super().get_context(data, accepted_media_type, renderer_context)
        request = context["request"]
        context["directory"] = get_directory(request)
        return context
