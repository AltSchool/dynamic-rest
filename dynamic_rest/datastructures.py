"""This module contains data structures for DREST."""

from django.utils import six


class TreeMap(dict):
    """Tree structure implemented with nested dictionaries."""

    def get_paths(self):
        """Get all paths from the root to the leaves.

        Returns:
            A list of lists of paths.
            E.g. [['a', 'b', 'c']] for {'a':{'b':{'c':None}}}
        """
        paths = []
        for key, child in six.iteritems(self):
            if isinstance(child, TreeMap) and child:
                # current child is an intermediate node
                for path in child.get_paths():
                    path.insert(0, key)
                    paths.append(path)
            else:
                # current child is an endpoint
                paths.append([key])
        return paths

    def insert(self, parts, leaf_value, update=False):
        """Add a list of nodes into the tree.

        The list will be converted into a TreeMap (chain) and then
        merged with the current TreeMap.

        For example, this would insert ['a','b','c'] as {'a':{'b':{'c':{}}}}
        into an empty TreeMap.

        Arguments:
            parts: list of nodes representing a chain
            leaf_value: value to insert into the leaf of the chain
            update: whether or not to update the leaf with the given value or
                to replace the value. Default: False (replace)
        """
        tree = self
        if not parts:
            return tree

        cur = tree
        last = len(parts) - 1
        for i, part in enumerate(parts):
            if part not in cur:
                cur[part] = TreeMap() if i != last else leaf_value
            elif i == last:  # found leaf
                if update:
                    cur[part].update(leaf_value)
                else:
                    cur[part] = leaf_value

            cur = cur[part]

        return self
