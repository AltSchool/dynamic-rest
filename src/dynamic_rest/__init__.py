"""Dynamic REST (or DREST) is an extension of Django REST Framework.

DREST offers the following features on top of the standard DRF kit:

- Linked/embedded/sideloaded relationships
- Field inclusions/exlusions
- Field-based filtering/sorting
- Directory panel for the browsable API
- Optimizations
"""

default_app_config = "src.dynamic_rest.apps.DynamicRestConfig"

# Version of the package
__version__ = "2023.11-alpha7"
