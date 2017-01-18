def unpack(content):
    keys = [k for k in content.keys() if k != 'meta']
    return content[keys[0]]
