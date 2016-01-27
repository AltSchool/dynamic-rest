from __future__ import absolute_import
import json
from collections import defaultdict
from rest_framework.test import APITestCase
from datetime import datetime

from .models import (
    User,
    Group,
    Permission
)

# BENCHMARKS: configuration for benchmarks
BENCHMARKS = [
    {
        # name: benchmark name
        'name': 'simple',
        # drest: DREST endpoint
        'drest': '/drest/users/',
        # drf: DRF endpoint
        'drf': '/drf/users/',
        # min_size: minimum sample size
        'min_size': 1,
        # max_size: maximum sample size
        'max_size': 20,
        # multiplier: number of records in one sample
        'multiplier': 20,
        # samples: number of samples to take
        'samples': 1
    },
    {
        'name': 'nested',
        'drest': '/drest/users?include[]=groups.',
        'drf': '/drf/users_with_groups/',
        'min_size': 1,
        'max_size': 20,
        'multiplier': 20,
        'samples': 1
    },
    {
        'name': 'deep',
        'drest': (
            '/drest/users/'
            '?include[]=groups.permissions.&include[]=permissions.'
        ),
        'drf': '/drf/users_with_all/',
        'min_size': 1,
        'max_size': 10,
        'multiplier': 1,
        'samples': 1
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
                type: 'bar',
            }},
            title: {{
                text: '{benchmark_name}',
                x: -20 //center
            }},
            xAxis: {{
                title: {{
                    text: '# of primary records'
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


class BenchmarkTest(APITestCase):

    @classmethod
    def setUpClass(cls):
        # initialize results: a 3x nested dictionary
        cls._results = defaultdict(lambda: defaultdict(dict))

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
                    data.append({
                        'name': implementation_name,
                        'data': sorted(implementation_data.items())
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
        samples
    ):
        data = []
        for _ in xrange(samples):
            # take the average over MULT_RUN runs
            start = datetime.now()
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            end = datetime.now()
            diff = end - start
            data.append(diff.total_seconds())

        self._results[benchmark_name][implementation_name][size] = (
            sum(data) / samples
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


def generate_test(name, title, drest, drf, size, samples):
    def test(self):
        getattr(self, 'generate_%s' % name)(size)
        self.bench('DREST', title, drest, size, samples)
        self.bench('DRF', title, drf, size, samples)
    return test

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
        test_name = 'test_%s_%d' % (name, size)
        test = generate_test(name, title, drest, drf, size, samples)
        setattr(BenchmarkTest, test_name, test)
