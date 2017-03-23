1.6.3

- Added `ENABLE_SELF_LINKS` option, default False.
  When enabled, links will include reference to the current resource.

- Made `serializer_class` optional on `DynamicRelationField`.
  `DynamicRelationField` will attempt to infer `serializer_class` from the
  `source` using `DynamicRouter.get_canonical_serializer`.

- Added `getter`/`setter` support to `DynamicRelationField`, allowing
  for custom relationship getting and setting. This can be useful for simplifying 
  complex "through"-relations.
