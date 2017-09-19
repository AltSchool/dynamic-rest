# 2.0.0
Major release

## Fields

- `dynamic_rest.fields.DynamicRelationField`
    - New initialization arguments: *`getter`* and *`setter`*
        Allows for custom relationship getting and setting.
        This can be useful for simplifying complex "through" relations.

    - Argument change: *`serializer_class`* is now optional
        DynamicRelationField` will attempt to infer `serializer_class` from the
        given source using `DynamicRouter.get_canonical_serializer`.

- New dynamic model fields: *`dynamic_rest.fields.model`*
    These fields add dynamic-value support to base DRF fields.
    Dynamic values are values that can contain metadata used
    by higher-level renderers (admin), such as styling directives.
    At a lower-level (JSON), only the base value is rendered.
    See `dynamic_rest.fields.DynamicChoicesField`.

## Serializers

- New setting: *`ENABLE_SELF_LINKS`*
    When enabled, links in representation will include reference to the current resource.
    Default is False.

- New serializer fields, see *`dynamic_rest.fields.model`*
    These fields extend the base DRF fields with dynamic value behavior.

- New serializer method: *`get_url`*
    Returns a URL to the serializer's collection or detail endpoint,
    dependening on whether a PK is passed in.

    The URL key can be injected into the serializer by the router when
    the serializer's view is registered.
    If not, this method will fallback to `DynamicRouter.get_canonical_url`.

- New serializer method: *`get_field`*
    Returns a serializer field

- New serializer method: *`resolve`*
    Provides a consistent way to resolve an API-field
    into a chain of model fields. Returns a model field list
    and serializer field list.

    For example, consider the API field `creator.location_name`
    on a `BlogSerializer` and underlying model path 
    `user.location.name` starting from the `Blog` model.
    `BlogSerializer.resolve("creator.location_name")`
    will return two paths of model and serializer fields necessary
    to "reach" the field from the serializer.

    ```
        [
            ("user", blog.user),
            ("location", user.location),
            ("name", location.name)
        ],
        [
            ("creator", DynamicRelationField("UserSerializer", source="user")),
            ("location_name", DynamicCharField(source="location.name"))
        ]
    ```

    Note that the lists do not necessarily contain the same number of elements
    because API fields can reference nested model fields.

    Calling resolve on a method field (`source == '*'`) will cause an exception.

- New serializer functionality: *nested updates*
    DREST serializers will now attempt to properly handle
    nested-source fields during updates.
    
    For example, if there is a user with related `profile`,
    a `UserSerializer` for the user can support updates
    to the related profile phone by creating a field with
    the nested source "profile.phone". Updates to the phone field
    will be set on the profile object, which is then saved.

    If related objects do not exist, the serializer will attempt
    to craete it using the fields in the request.
    Multiple fields on a related model can be mapped to.

- New serializer method: *`needs_prefetch`*
    This method allows a serializer to specify whether its
    source should be prefetched.

    This is only relevant to model serializers which are being handled
    by DREST views: if this method returns True, the underlying object
    will be added to the prefetch tree by the DREST query backend.

## Views

- Fixed `sort[]` behavior around rewrites
    API-name to model-name rewrites are now properly handled by `sort[]`.

- New views: *`dynamic_rest.login`* and *`dynamic_rest.logout`*
    Wraps `django.contrib.auth.views` login and logout
    using the DREST admin login template.

## Routers

- Renamed option: `ROOT_VIEW_NAME` renamed to *`API_NAME`*
    Human-friendly name of the API.

- New option: *`API_DESCRIPTION`*
    Human-friendly description of the API.

- New option: *`API_ROOT_SECURE`*
    If enabled, the root view will redirect if the user is not authenticated.
    Default is False.

## Renderers

- New renderer: *`dynamic_rest.renderers.DynamicAdminRenderer`*
    Extends `rest_framework.renderers.AdminRenderer`, adding a
    new, responsively designed admin UI that integrates with DREST filters
    and relationships.
    
    Serializers from 1.x should work as expected, but are recommended to set
    the following configuration options in their `Meta` class to support an
    ideal experience.

    - *`name_field`*: a human-friendly field name for records
        - defaults to the model PK
        - used for relationship lookup and representation
        - e.g. `"name"`
    - *`search_key`*: a filter key to search against to find records of this resource
        - defaults to None
        - used for search
        - e.g: `"filter{name.icontains}"`
    - *`list_fields`*: a list of fields to display within long lists
        - defaults to all fields
        - used for displaying the list view
        - e.g. `["name", "description"]`
    - *`description`*: a description of the resource
        - e.g: "The Build resource represents a backend build."

- New option: *`ADMIN_LOGIN_URL`*
    The login URL to use within admin UI.

- New option: *`ADMIN_LOGOUT_URL`*
    The logout URL to use within admin UI.

- New option: *`ADMIN_TEMPLATE`*
    Template file name for the admin view.
    Defaults to "dynamic_rest/admin.html"

    Customizations are possible by settings `ADMIN_TEMPLATE` to an
    application-specific template, e.g. "app/admin.html".

    Common blocks to override: `bootstrap_css`, `brand`.
    The UI is implemented in Bootstrap 4.

- New option: *`ADMIN_LOGIN_TEMPLATE`*
    Template file name for the admin login view.
    Defaults to "dynamic_rest/login.html"
