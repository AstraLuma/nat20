from pprint import pprint

from sphinx.util.inventory import InventoryFile

with open('./_build/html/objects.inv', 'rb') as invfile:
    inv = InventoryFile.load(invfile, '', lambda a, b: b)

# {<domain:kind>: {<name>: tuple}}
for prefix, items in inv.items():
    for name, info in items.items():
        print(f"{prefix}:{name}: {info!r}")
