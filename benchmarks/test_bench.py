from __future__ import absolute_import

import json
import pkg_resources
import random
import string
from collections import defaultdict
from datetime import datetime

from rest_framework.test import APITestCase

from .models import Group, Permission, User


# Python 3 compatibility
try:
    xrange
except NameError:
    xrange = range

DREST_VERSION = pkg_resources.require('dynamic-rest')[0].version
DRF_VERSION = pkg_resources.require('djangorestframework')[0].version
AVERAGE_TYPE = 'median'

# BENCHMARKS: configuration for benchmarks
BENCHMARKS = [
    {
        # name: benchmark name
        'name': 'linear',
        # drest: DREST endpoint
        'drest': '/drest/users/',
        # drf: DRF endpoint
        'drf': '/drf/users/',
        # min_size: minimum sample size
        'min_size': 1,
        # max_size: maximum sample size
        'max_size': 16,
        # multiplier: number of records in one sample
        'multiplier': 256,
        # samples: number of samples to take
        'samples': 12
    },
    {
        'name': 'quadratic',
        'drest': '/drest/users?include[]=groups.',
        'drf': '/drf/users_with_groups/',
        'min_size': 1,
        'max_size': 16,
        'multiplier': 4,
        'samples': 12
    },
    {
        'name': 'cubic',
        'drest': (
            '/drest/users/'
            '?include[]=groups.permissions.'
        ),
        'drf': '/drf/users_with_all/',
        'min_size': 1,
        'max_size': 16,
        'multiplier': 1,
        'samples': 12
    }
]

CHART_HEAD = """
<head>
    <script src="https://code.jquery.com/jquery-1.12.0.min.js"></script>
    <script src="https://code.highcharts.com/highcharts.js"></script>
</head>
"""

CHART_TEMPLATE = """
<script>
    $(function () {{
        var {benchmark_name}_chart = new Highcharts.Chart({{
            chart: {{
                renderTo: '{benchmark_name}',
                type: 'line',
            }},
            title: {{
                text: '{benchmark_name}',
                x: -20 //center
            }},
            xAxis: {{
                title: {{
                    text: '# of records'
                }}
            }},
            yAxis: {{
                title: {{
                    text: 'Response time (seconds)'
                }},
                plotLines: [{{
                    value: 0,
                    width: 1,
                    color: '#808080'
                }}]
            }},
            legend: {{
                layout: 'vertical',
                align: 'right',
                verticalAlign: 'middle',
                borderWidth: 0
            }},
            series: {data}
        }});
    }});
</script>
<div id="{benchmark_name}" style="width:100%"></div>
<br/>
"""


def get_average(values):
    l = len(values)
    if l == 0:
        return 0
    elif AVERAGE_TYPE == 'mean':
        return sum(values) / l
    elif AVERAGE_TYPE == 'median':
        values = sorted(values)
        if len(values) % 2 == 1:
            return values[((l + 1) / 2) - 1]
        else:
            return float(
                sum(
                    values[(l / 2) - 1:(l / 2) + 1]
                )
            ) / 2.0


class BenchmarkTest(APITestCase):

    @classmethod
    def setUpClass(cls):
        # initialize results: a 4x nested dictionary
        cls._results = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    dict
                )
            )
        )

    @classmethod
    def tearDownClass(cls):
        # save results to an HTML file
        with open('benchmarks.html', 'w') as file:
            file.write(CHART_HEAD)
            for benchmark_name, implementations in sorted(
                cls._results.items()
            ):
                data = []
                for implementation_name, implementation_data in sorted(
                    implementations.items()
                ):
                    for key in implementation_data.keys():
                        values = sorted(implementation_data[key].values())
                        implementation_data[key] = get_average(values)

                    implementation_data = sorted(implementation_data.items())

                    data.append({
                        'name': implementation_name,
                        'data': implementation_data
                    })

                file.write(
                    CHART_TEMPLATE.format(
                        benchmark_name=benchmark_name,
                        data=json.dumps(data)
                    )
                )

    def bench(
        self,
        implementation_name,
        benchmark_name,
        url,
        size,
        sample
    ):
        start = datetime.now()
        response = self.client.get(url)
        end = datetime.now()
        self.assertEqual(response.status_code, 200)
        diff = end - start
        d = diff.total_seconds()
        self._results[benchmark_name][implementation_name][size][sample] = d

    def generate_linear(self, size):
        total = 0
        for i in xrange(size):
            total += 1
            User.objects.create(
                name=str(i)
            )
        return total

    def generate_quadratic(self, size):
        total = 0
        for i in xrange(size):
            total += 1
            user = User.objects.create(
                name=str(i)
            )
            for j in xrange(size):
                total += 1
                group = Group.objects.create(
                    name='%d-%d' % (i, j),
                    max_size=size
                )
                user.groups.add(group)
        return total

    def generate_cubic(self, size):
        total = 0
        for i in xrange(size):
            total += 1
            user = User.objects.create(
                name=str(i)
            )
            for j in xrange(size):
                total += 1
                group = Group.objects.create(
                    name='%d-%d' % (i, j),
                    max_size=size
                )
                user.groups.add(group)
                for k in xrange(size):
                    total += 1
                    permission = Permission.objects.create(
                        name='%d-%d-%d' % (i, j, k)
                    )
                    group.permissions.add(permission)
        return total


def generate_benchmark(name, title, drest, drf, size, sample):
    def bench(self):
        total_size = getattr(self, 'generate_%s' % name)(size)
        self.bench(
            'DREST %s' % DREST_VERSION,
            title,
            drest,
            total_size,
            sample
        )
        self.bench('DRF %s' % DRF_VERSION, title, drf, total_size, sample)
    return bench


def get_random_string(size):
    return ''.join(
        random.choice(string.ascii_uppercase)
        for _ in xrange(size)
    )

# generate test methods
for benchmark in BENCHMARKS:
    name = benchmark['name']
    title = name.title()
    min_size = benchmark['min_size']
    max_size = benchmark['max_size']
    drf = benchmark['drf']
    drest = benchmark['drest']
    multiplier = benchmark['multiplier']
    samples = benchmark['samples']

    for size in range(min_size, max_size + 1):
        size *= multiplier
        for sample in xrange(samples):
            test_name = 'test_%s_%s_%d_%d' % (
                get_random_string(4), name, size, sample
            )
            test = generate_benchmark(name, title, drest, drf, size, sample)
            setattr(BenchmarkTest, test_name, test)
