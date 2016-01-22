# Dynamic REST

[![Circle CI](https://circleci.com/gh/AltSchool/dynamic-rest.svg?style=svg)](https://circleci.com/gh/AltSchool/dynamic-rest)

**Dynamic API extensions for Django REST Framework**

See http://dynamic-rest.readthedocs.org for full documentation.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
# Table of Contents

- [Maintainers](#maintainers)
- [Overview](#overview)
- [Requirements](#requirements)
- [Compatability Table](#compatability-table)
- [Installation](#installation)
- [Demo](#demo)
- [Features](#features)
  - [Linked relationships](#linked-relationships)
  - [Sideloaded relationships](#sideloaded-relationships)
  - [Embedded relationships](#embedded-relationships)
  - [Field inclusions](#field-inclusions)
  - [Field exclusions](#field-exclusions)
  - [Field-based filtering](#field-based-filtering)
  - [Field-based ordering](#field-based-ordering)
  - [Directory panel for your Browsable API](#directory-panel-for-your-browsable-api)
  - [Optimizations at the query and serializer layers](#optimizations-at-the-query-and-serializer-layers)
- [Settings](#settings)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Maintainers

* [Anthony Leontiev](mailto:ant@altschool.com)
* [Ryo Chijiiwa](mailto:ryo@altschool.com)

# Overview

Dynamic REST (or DREST) extends the popular [Django REST Framework](https://django-rest-framework.org) (or DRF) with API features that
empower your simple RESTful APIs with the flexibility of a graph query language.

DREST classes can be used as a drop-in replacement for DRF classes, which offer the following features on top of the standard DRF kit:

* Linked relationships
* Sideloaded relationships
* Embedded relationships 
* Field inclusions
* Field exclusions
* Field-based filtering
* Field-based sorting
* Directory panel for your Browsable API
* Optimizations at the query and serializer layers

DREST was initially written to complement [Ember Data](https://github.com/emberjs/data),
but it can be used to provide fast and flexible CRUD operations to any consumer that supports JSON and HTTP.

# Requirements

* Python (2.7, 3.3, 3.4, 3.5)
* Django (1.7, 1.8, 1.9)
* Django REST Framework (3.1, 3.2, 3.3)

# Compatability Table

Not all versions of Python, Django, and DRF are compatible. Here are the combinations you can use reliably with DREST (all tested by our tox configuration):

| Python | Django | DRF | OK  |
| ------ | ------ | --- | --- |
| 2.7    | 1.7    | 3.1 | YES |
| 2.7    | 1.7    | 3.2 | YES |
| 2.7    | 1.7    | 3.3 | YES |
| 2.7    | 1.8    | 3.1 | YES |
| 2.7    | 1.8    | 3.2 | YES |
| 2.7    | 1.8    | 3.3 | YES |
| 2.7    | 1.9    | 3.1 | NO<sup>1</sup> |
| 2.7    | 1.9    | 3.2 | YES |
| 2.7    | 1.9    | 3.3 | YES |
| 3.3    | 1.7    | 3.1 | YES |
| 3.3    | 1.7    | 3.2 | YES |
| 3.3    | 1.7    | 3.3 | YES |
| 3.3    | 1.8    | 3.1 | YES |
| 3.3    | 1.8    | 3.2 | YES |
| 3.3    | 1.8    | 3.3 | YES |
| 3.3    | 1.9    | 3.1 | NO<sup>1,2</sup> |
| 3.3    | 1.9    | 3.2 | NO<sup>2</sup> |
| 3.3    | 1.9    | 3.3 | NO<sup>2</sup> |
| 3.4    | 1.7    | 3.1 | YES |
| 3.4    | 1.7    | 3.2 | YES |
| 3.4    | 1.7    | 3.3 | YES |
| 3.4    | 1.8    | 3.1 | YES |
| 3.4    | 1.8    | 3.2 | YES |
| 3.4    | 1.8    | 3.3 | YES |
| 3.4    | 1.9    | 3.1 | NO<sup>1</sup> |
| 3.4    | 1.9    | 3.2 | YES |
| 3.4    | 1.9    | 3.3 | YES |
| 3.5    | 1.7    | 3.1 | NO<sup>3</sup> |
| 3.5    | 1.7    | 3.2 | NO<sup>3</sup> |
| 3.5    | 1.7    | 3.3 | NO<sup>3</sup> |
| 3.5    | 1.8    | 3.1 | YES |
| 3.5    | 1.8    | 3.2 | YES |
| 3.5    | 1.8    | 3.3 | YES |
| 3.5    | 1.9    | 3.1 | NO<sup>1</sup> |
| 3.5    | 1.9    | 3.2 | YES |
| 3.5    | 1.9    | 3.3 | YES |

* 1: Django 1.9 is not compatible with DRF 3.1
* 2: Django 1.9 is not compatible with Python 3.3
* 3: Django 1.7 is not compatible with Python 3.5

# Installation

1) Install using `pip`:

```bash
    pip install dynamic-rest
```

(or add `dynamic-rest` to your `requirements.txt` file or `setup.py` file)

2) Add `rest_framework` and `dynamic_rest` to your `INSTALLED_APPS`:

```python
    INSTALLED_APPS = (
        ...
        'rest_framework',
        'dynamic_rest'
    )

```

# Demo

This repository comes with a `tests` package that also serves as a demo application.
This application is hosted at `dynamic-rest.herokuapp.com` but can also be run locally:

1) Clone this repository:

```bash
    git clone git@github.com:AltSchool/dynamic-rest.git
    cd dynamic-rest
```

2) From within the repository root, start the demo server:

```bash
    make serve
```

3) Visit `localhost:9001` in your browser.

# Features

To understand the DREST API features, lets consider a demo model with a corresponding viewset, serializer, and route.
This will look very familiar to anybody who has worked with DRF:

```python
# The related LocationSerializer and GroupSerializer are omitted for brevity

# The Model
class User(models.Model):
    name = models.TextField()
    location = models.ForeignKey('Location')
    groups = models.ManyToManyField('Group')

# The Serializer
class UserSerializer(DynamicModelSerializer):
    class Meta:
        model = User
        name = 'user'
        fields = ("id", "name", "location", "groups")

    location = DynamicRelationField('LocationSerializer')
    groups = DynamicRelationField('GroupSerializer', many=True)

# The ViewSet
class UserViewSet(DynamicModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()

# The Router
router = DynamicRouter()
router.register('/users', UserViewSet)
```

## Linked relationships

One of the key features of the DREST serializer layer is the ability to represent relationships in different ways, depending on the request context (external requirements) and the code context (internal requirements).

By default, a "has-one" (or "belongs-to") relationship like a user's "location" will be represented as the value of the related location object's ID.
A "has-many" relationship like a user's "groups" will be represented as a list of all related group object IDs.

When a relationship is represented in this way, DREST automatically includes relationship links in the API response representing the object:

```
-->
    GET /users/1/
<--
    200 OK
    {
        "user": {
            "id": 1,
            "name": "John",
            "location": 1,
            "groups": [1, 2],
            "links": {
                "location": "/users/1/location",
                "groups": "/users/1/groups"
            }
        }
    }
```

An API consumer can navigate to these relationship endpoints in order to obtain information about the related records. DREST will automatically create
the relationship endpoints for you -- no additional code is required:

```
-->
    GET /users/1/location
<--
    200 OK
    {
        "location": {
            "id": 1,
            "name": "New York"
        }
    }
```

## Sideloaded relationships

Using linked relationships provides your API consumers with a "lazy-loading" mechanism for traversing through a graph of data: the consumer can first load the primary resource, like the user, and then load related resources later, if necessary.

In some situations, it can be more efficient to load relationships eagerly, such that a user's groups are available immediately as soon as the user is loaded. In Django, this can be accomplished by using [prefetch_related](https://docs.djangoproject.com/en/1.9/ref/models/querysets/#django.db.models.query.QuerySet.prefetch_related) or [select_related](https://docs.djangoproject.com/en/1.9/ref/models/querysets/#select-related).

In DREST, the requirement to eagerly load (or "sideload") relationships can be expressed with the `include[]` query parameter. If a consumer wants to fetch a user and sideload their groups, for example, they would make a request like this:

```
--> 
    GET /users/1/?include[]=groups.
<--
    200 OK
    {
        "user": {
            "id": 1,
            "name": "John",
            "location": 1,
            "groups": [1, 2],
            "links": {
                "location": "/users/1/location"
            }
        },
        "groups": [{
            "id": 1,
            "name": "Family",
            "location": 2,
            "links": {
                "location": "/groups/1/location"
            }
        }, {
            "id": 2,
            "name": "Work",
            "location": 3,
            "links": {
                "location": "/groups/2/location"
            }
        }]
    }
```

The "user" portion of the request looks nearly identical to the linked relationship response: the groups are still represented by their IDs. However, instead of including a link to the groups endpoint, the group data is present within the respones itself, under a top-level "groups" key.

Note that each group itself contains relationships to "location", which are linked in this case. Can we sideload those locations as well? 

Yes! With DREST, it is possible to sideload as many relationships as you'd like, as deep as you'd like. For example, in this request, we obtain the user with his groups, his locations, and his groups' locations all sideloaded in the same response:

```
--> 
    GET /users/1/?include[]=groups.location.&include[]=location.
<--
    200 OK
    {
        "user": {
            "id": 1,
            "name": "John",
            "location": 1,
            "groups": [1, 2]
        },
        "groups": [{
            "id": 1,
            "name": "Family",
            "location": 2,
        }, {
            "id": 2,
            "name": "Work",
            "location": 3,
        }],
        "locations": [{
            "id": 1,
            "name": "New York"
        }, {
            "id": 2,
            "name": "New Jersey"
        }, {
            "id": 3,
            "name": "California"
        }]
    }
```

## Embedded relationships

If you want your relationships loaded in the same request but don't want them sideloaded in the top-level, you can instruct your serializer to embed relationships instead. 

In that case, the demo serializer above would look like this:

```python

# The Serializer
class UserSerializer(DynamicModelSerializer):
    class Meta:
        model = User
        name = 'user'
        fields = ("id", "name", "location", "groups")

    location = DynamicRelationField('LocationSerializer', embed=True)
    groups = DynamicRelationField('GroupSerializer', embed=True, many=True)

```

... and the call above would return a response with relationships embedded in place of the usual ID representation:

```
--> 
    GET /users/1/?include[]=groups.
<--
    200 OK
    {
        "user": {
            "id": 1,
            "name": "John",
            "location": 1,
            "groups": [{
                "id": 1,
                "name": "Family",
                "location": 2,
                "links": {
                    "location": "/groups/1/location"
                }
            }, {
                "id": 2,
                "name": "Work",
                "location": 3,
                "links": {
                    "location": "/groups/2/location"
                }
            }],
            "links": {
                "location": "/users/1/location"
            }
        }
    }
```

In DREST, sideloading is the default because it can produce much smaller payloads in circumstances where related objects are referenced more than once in the response.

For example, if you requested a list of 10 users along with their groups, and those users all happened to be in the same groups, the embedded variant would represent each group 10 times. The sideloaded variant will only represent a particular group once, regardless of the number of times that group is referenced.

## Field inclusions 

You can use the `include[]` feature not only to sideload relationships, but also to load basic fields that are marked "deferred".

In DREST, any field or relationship can be marked deferred, which will indicate to the framework that the field should only be returned when requested by `include[]`. This could be a good option for fields with large values that are not always relevant in a general context.

For example, a user might have a "personal_statement" field that we would want to defer. At the serializer layer, that would look like this:

```python

# The Serializer
class UserSerializer(DynamicModelSerializer):
    class Meta:
        model = User
        name = 'user'
        fields = ("id", "name", "location", "groups", "personal_statement")
        deferred_fields = ("personal_statement", )
    
    location = DynamicRelationField('LocationSerializer')
    groups = DynamicRelationField('GroupSerializer', many=True)

```

This field will only be returned if requested:

```
-->
    GET /users/1/?include[]=personal_statement
<--
    200 OK
    {
        "user": {
            "id": 1,
            "name": "John",
            "location": 1,
            "groups": [1, 2],
            "personal_statement": "Hello, my name is John and I like........",
            "links": {
                "location": "/users/1/location",
                "groups": "/users/1/groups"
            }
        }
    }
```

Note that `include[]=personal_statement` does not have a `.` following the field name as in the previous examples for embedding and sideloading relationships. This allows us to differentiate between cases where we have a deferred relationship and want to include the relationship IDs as opposed to including and also sideloading the relationship. 

For example, if the user had a deferred "events" relationship, passing `include[]=events` would return an "events" field populated by event IDs, passing `include[]=events.` would sideload or embed the events themselves, and by default, only a link to the events would be returned. This can be useful for large has-many relationships.

## Field exclusions

Just as deferred fields can be included on demand with the `include[]` feature, fields that are not deferred can be excluded with the `exclude[]` feature. Like `include[]`, `exclude[]` also supports multiple values and dot notation to allow you to exclude fields on sideloaded relationships.

For example, if we want to fetch a user with his groups, but ignore the groups' location and user's location, we could make a request like this:

```
-->
    GET /users/1/?include[]=groups.&exclude[]=groups.location&exclude[]=location
<--
    200 OK
    {
        "user": {
            "id": 1,
            "name": "John",
            "groups": [1, 2],
            "links": {
                "location": "/users/1/location"
            }
        },
        "groups": [{
            "id": 1,
            "name": "Family",
            "links": {
                "location": "/groups/1/location"
            }
        }, {
            "id": 2,
            "name": "Work",
            "links": {
                "location": "/groups/2/location"
            }
        }]
    }
```

`exclude[]` supports the wildcard value: `*`, which means "don't return anything".
Why is that useful? `include[]` overrides `exclude[]`, so `exclude[]=*` can be combined with `include[]` to return only a single value or set of values from a resource.

For example, to obtain only the user's name:

```
-->
    GET /users/1/?exclude[]=*&include[]=name
<--
    200 OK
    {
        "user": {
            "name": "John",
            "links": {
                "location": "/users/1/location",
                "groups": "/users/1/groups"
            }
        }
    }
```

Note that `links` will always be returned, even if the underlying field is excluded.

## Field-based filtering

Tired of writing custom filters for all of your fields? DREST has your back with the `filter{}` feature.

You can filter a user by his name (exact match):

```
-->
    GET /users/?filter{name}=John
<--
    200 OK
    ...
```

... or a partial match:

```
--> 
   GET /users/?filter{name.icontains}=jo
<--
    200 OK
    ...
```

... or one of several names:

```
-->
    GET /users/?filter{name.in}=John&filter{name.in}=Joe
<--
    200 OK
```

... or a relationship ID:

```
-->
    GET /users/?filter{groups}=1
<--
    200 OK
```

... or lack thereof:

```
-->
    GET /users/?filter{-groups}=1
<--
    200 OK
```

... or a relationship field:

```
-->
    GET /users/?filter{groups.name}=Home
<--
    200 OK
```

... or multiple criteria:

```
-->
    GET /users/?filter{groups.name}=Home&filter{name}=John
<--
    200 OK
```

... or combine it with `include[]` to filter the sideloaded data (get all the users and only sideload certain groups):

```
-->
    GET /users/?include[]=groups.&filter{groups.name.icontains}=h
<--
    200 OK
```

The sky is the limit! DREST supports just about every basic filtering scenario and operator that you can use in Django:

* in
* icontains
* istartswith
* range
* lt
* gt
...

See the [full list here](https://github.com/AltSchool/dynamic-rest/blob/master/dynamic_rest/filters.py#L104).

## Field-based ordering

You can use the `sort[]` feature to order your response by one or more fields. Dot notation is supported for sorting by nested properties:

```
-->
    GET /users/?sort[]=name&sort[]=groups.name
<--
    200 OK
    ...
```

## Directory panel for your Browsable API

We love the DRF browsable API, but wish that it included a directory that would let you see your entire list of endpoints at a glance from any page.
DREST adds that in:

[TODO: SCREENSHOT OF DIRECTORY]

## Optimizations at the query and serializer layers

Supporting nested sideloading and filtering is expensive and can lead to very poor query performance if done naively.
DREST uses Django's [Prefetch](https://docs.djangoproject.com/en/1.9/ref/models/querysets/#django.db.models.Prefetch) object to prevent N+1 query situations and guarantee that your API is performant. 
We also optimize the serializer layer to ensure that the conversion of model data into JSON is as fast as possible.

How fast is it? Here are some benchmarks that compare DREST response time to DRF response time:

[TODO: BENCHMARKS]

# Settings

DREST is configurable, and all settings are nested under a single block in your `settings.py` file. Here it is with default values:

```python

DYNAMIC_REST = {
    'DEBUG': False, # enable/disable internal debugging,
    'ENABLE_BROWSABLE_API': True, # enable/disable the browsable API. it can be useful to disable in production
    'ENABLE_LINKS': True, # enable/disable relationship links
    'ENABLE_SERIALIZER_CACHE: True, # enable/disable caching of related serializers
    'MAX_PAGE_SIZE': None, # global setting for max page size, can be overridden at the viewset level
    'PAGE_QUERY_PARAM': 'page', # global setting for the pagination query parameter, can be overridden at the viewset level
    'PAGE_SIZE_QUERY_PARAM': 'per_page', # global setting for the page size query parameter, can be overriden at the global level
}
```
