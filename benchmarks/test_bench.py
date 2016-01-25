from __future__ import absolute_import
from collections import defaultdict
from rest_framework.test import APITestCase
from datetime import datetime
from .models import (
    User,
    Group,
    Permission
)

MULT_SIMPLE_SIZE = 10
MIN_SIMPLE_SIZE = 1
MAX_SIMPLE_SIZE = 10

MULT_NESTED_SIZE = 10
MIN_NESTED_SIZE = 1
MAX_NESTED_SIZE = 10

MULT_DEEP_SIZE = 10
MIN_DEEP_SIZE = 10
MAX_DEEP_SIZE = 20

MULT_RUN = 1


class BenchmarkTest(APITestCase):

    def setUp(self):
        self._results = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    list
                )
            )
        )

    def tearDown(self):
        for implementation_name, benchmarks in self._results.items():
            for benchmark_name, benchmark in sorted(benchmarks.items()):
                for size, value in sorted(benchmark.items()):
                    value = ','.join([str(v) for v in value])
                    print(
                        '%s,%s,%s,%s' % (
                            implementation_name,
                            benchmark_name,
                            str(size),
                            value
                        )
                    )

    def bench(self, implementation_name, benchmark_name, url, size):
        for _ in xrange(MULT_RUN):

            start = datetime.now()
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            end = datetime.now()
            diff = end - start

            self._results[implementation_name][benchmark_name][size].append(
                diff.total_seconds()
            )

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
                user.permissions.add(permission)
                user.groups.add(group)
                for k in xrange(size):
                    permission = Permission.objects.create(
                        name='%d-%d-%d' % (i, j, k)
                    )
                    group.permissions.add(permission)

    def test_simple(self):
        for size in range(MIN_SIMPLE_SIZE, MAX_SIMPLE_SIZE+1):
            size *= MULT_SIMPLE_SIZE
            self.generate_simple(size)
            self.bench('drest', 'simple', '/drest/users/', size)
            self.bench('drf', 'simple', '/drf/users/', size)

    def test_nested(self):
        for size in range(MIN_NESTED_SIZE, MAX_NESTED_SIZE+1):
            size *= MULT_NESTED_SIZE
            self.generate_nested(size)
            self.bench(
                'drest',
                'nested',
                '/drest/users/?include[]=groups.',
                size
            )
            self.bench(
                'drf',
                'nested',
                '/drf/users_with_groups/',
                size
            )

    def test_deep(self):
        for size in range(MIN_DEEP_SIZE, MAX_DEEP_SIZE+1):
            size *= MULT_DEEP_SIZE
            self.generate_deep(size)
            self.bench(
                'drest',
                'deep',
                '/drest/users/'
                '?include[]=groups.permissions.&include[]=permissions.',
                size
            )
            self.bench(
                'drf',
                'deep',
                '/drf/users_with_all/',
                size
            )
