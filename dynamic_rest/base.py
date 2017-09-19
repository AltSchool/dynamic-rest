class DynamicBase(object):
    def is_admin(self):
        """Whether or not this field is being rendered by an admin view."""
        context = getattr(self, 'context', None)
        if not context:
            return False

        request = context.get('request')
        if not request:
            return False

        renderer = request.accepted_renderer
        return renderer.format == 'admin'
