"""DRF Compatibility."""
from rest_framework import __version__ as drf_version

try:
    from rest_framework.fields import BooleanField, NullBooleanField
except ImportError:
    # DRF >= 3.14.0
    from rest_framework.fields import BooleanField


DRF_VERSION = drf_version.split(".")
if int(DRF_VERSION[0]) >= 3 and int(DRF_VERSION[1]) >= 14:
    # NullBooleanField deprecated in DRF >= 3.14
    RestFrameworkBooleanField = BooleanField
else:
    RestFrameworkBooleanField = (BooleanField, NullBooleanField)
