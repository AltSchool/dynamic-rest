def merge_link_object(serializer, data, instance):
    """Add a 'links' attribute to the data that maps field names to URLs.

    NOTE: This is the format that Ember Data supports, but alternative
          implementations are possible to support other formats.
    """

    link_object = {}

    link_fields = serializer.get_link_fields()
    for name, field in link_fields.iteritems():
        # For included fields, omit link if there's no data.
        if name in data and not data[name]:
            continue

        # Default to DREST-generated relation endpoints.
        link = getattr(field, 'link', "%s/" % name)
        if callable(link):
            link = link(name, field, data, instance)

        link_object[name] = link

    if link_object:
        data['links'] = link_object
    return data
