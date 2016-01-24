from __future__ import absolute_import
from rest_framework.test import APITestCase
from datetime import datetime
from .models import (
    User,
    Group,
    Permission
)

MULT_SIMPLE_SIZE = 1
MIN_SIMPLE_SIZE = 10
MAX_SIMPLE_SIZE = 20

MULT_NESTED_SIZE = 1
MIN_NESTED_SIZE = 10
MAX_NESTED_SIZE = 20

MULT_DEEP_SIZE = 1
MIN_DEEP_SIZE = 10
MAX_DEEP_SIZE = 20


class BenchmarkTest(APITestCase):

    def time(self, key, url, size):
        start = datetime.now()

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        end = datetime.now()
        diff = end - start

        print("%s@%d: %d ms" % (key, size, diff.total_seconds() * 1000))

    def generate_simple(self, size):
        for i in xrange(size):
            User.objects.create(
                name=str(i)
            )

    def generate_nested(self, size):
        for i in xrange(size):
            user = User.objects.create(
                name=str(i)
            )
            for j in xrange(size):
                group = Group.objects.create(
                    name='%d-%d' % (i, j),
                    max_size=size
                )
                user.groups.add(group)

    def generate_deep(self, size):
        for i in xrange(size):
            user = User.objects.create(
                name=str(i)
            )
            for j in xrange(size):
                group = Group.objects.create(
                    name='%d-%d' % (i, j),
                    max_size=size
                )
                permission = Permission.objects.create(
                    name='%d-%d' % (i, j),
                )
                group.permissions.add(permission)
                user.groups.add(group)
                for k in xrange(size):
                    permission = Permission.objects.create(
                        name='%d-%d-%d' % (i, j, k)
                    )
                    group.permissions.add(permission)

    def test_simple(self):
        for size in range(MIN_SIMPLE_SIZE, MAX_SIMPLE_SIZE):
            size *= MULT_SIMPLE_SIZE
            self.generate_simple(size)
            self.time('drest/simple', '/drest/users/', size)
            self.time('drf/simple', '/drf/users/', size)

    def test_nested(self):
        for size in range(MIN_NESTED_SIZE, MAX_NESTED_SIZE):
            size *= MULT_NESTED_SIZE
            self.generate_nested(size)
            self.time('drest/nested', '/drest/users/?include[]=groups.', size)
            self.time('drf/nested', '/drf/users_with_groups/', size)

    def test_deep(self):
        for size in range(MIN_DEEP_SIZE, MAX_DEEP_SIZE):
            size *= MULT_DEEP_SIZE
            self.generate_deep(size)
            self.time(
                'drest/deep',
                '/drest/users/?include[]=groups.permissions.&include[]=permissions.',  # noqa
                size
            )
            self.time(
                'drf/deep',
                '/drf/users_with_all/',
                size
            )
