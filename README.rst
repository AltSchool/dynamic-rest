Dynamic REST
===================

**Dynamic API extensions for Django REST Framework**

See http://dynamic-rest.readthedocs.org for full documentation.

Overview
========

Dynamic REST (or DREST) extends the popular `Django REST
Framework <https://django-rest-framework.org>`__ (or DRF) with API
features that empower simple RESTful APIs with the flexibility of a
graph query language.

DREST classes can be used as a drop-in replacement for DRF classes,
which offer the following features on top of the standard DRF kit:

-  Linked relationships
-  Sideloaded relationships
-  Embedded relationships
-  Field inclusions
-  Field exclusions
-  Field-based filtering
-  Field-based sorting
-  Directory panel for your Browsable API
-  Optimizations

DREST was initially written to complement `Ember
Data <https://github.com/emberjs/data>`__, but it can be used to provide
fast and flexible CRUD operations to any consumer that supports JSON
over HTTP.

Maintainers
-----------

-  `Anthony Leontiev <mailto:aleontiev@tohigherground.com>`__
-  `Savinay Nangalia <mailto:snangalia@tohigherground.com>`__
-  `Christina D'Astolfo <mailto:cdastolfo@tohigherground.com>`__

Requirements
============

-  Python (3.6, 3.7, 3.8)
-  Django (2.2, 3.1, 3.2)
-  Django REST Framework (3.11, 3.12, 3.13)
