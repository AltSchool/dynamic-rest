class TreeMap(dict):
  """
  Basic nested-dict tree structure.
  """

  def insert(self, parts, leaf_value, update=False):
    """
    Convert ['a','b','c'] into {'a':{'b':{'c':{}}}}
    """
    tree = self 
    if not parts:
      return tree
    
    cur = tree
    last = len(parts) - 1
    for i,part in enumerate(parts):
      if part not in cur:
        cur[part] = TreeMap() if i!=last else leaf_value 
      elif i==last: # found leaf
        cur[part] = cur[part].update(leaf_value) if update else leaf_value

      cur = cur[part]

    return self 
