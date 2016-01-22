from django.utils import six


class TreeMap(dict):

    """
    Basic nested-dict tree structure.
    """

    def get_paths(self):
        """Get all paths down from the root.

        Returns [['a', 'b', 'c']] for {'a':{'b':{'c':None}}}
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
        """Convert ['a','b','c'] into {'a':{'b':{'c':{}}}}."""
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
