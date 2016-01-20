"""This module contains patches for Django issues.

These patches are meant to be short-lived and are
extracted from Django code changes.
"""


def patch_prefetch_one_level():
    """
    This patch address Django bug https://code.djangoproject.com/ticket/24873,
    which was merged into Django master
    in commit 025c6553771a09b80563baedb5b8300a8b01312f
    into django.db.models.query.

    The code that follows is identical to the code in the above commit,
    with all comments stripped out.
    """
    import copy

    def prefetch_one_level(instances, prefetcher, lookup, level):
        rel_qs, rel_obj_attr, instance_attr, single, cache_name = (
            prefetcher.get_prefetch_queryset(
                instances, lookup.get_current_queryset(level)))

        additional_lookups = [
            copy.copy(additional_lookup) for additional_lookup
            in getattr(rel_qs, '_prefetch_related_lookups', [])
        ]
        if additional_lookups:
            rel_qs._prefetch_related_lookups = []

        all_related_objects = list(rel_qs)

        rel_obj_cache = {}
        for rel_obj in all_related_objects:
            rel_attr_val = rel_obj_attr(rel_obj)
            rel_obj_cache.setdefault(rel_attr_val, []).append(rel_obj)

        for obj in instances:
            instance_attr_val = instance_attr(obj)
            vals = rel_obj_cache.get(instance_attr_val, [])
            to_attr, as_attr = lookup.get_current_to_attr(level)
            if single:
                val = vals[0] if vals else None
                to_attr = to_attr if as_attr else cache_name
                setattr(obj, to_attr, val)
            else:
                if as_attr:
                    setattr(obj, to_attr, vals)
                else:
                    qs = getattr(obj, to_attr).all()
                    qs._result_cache = vals
                    qs._prefetch_done = True
                    obj._prefetched_objects_cache[cache_name] = qs
        return all_related_objects, additional_lookups

    # apply the patch
    from django.db.models import query
    query.prefetch_one_level = prefetch_one_level
