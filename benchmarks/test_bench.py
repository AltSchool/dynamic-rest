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

MULT_SIMPLE_SIZE = 10
MIN_SIMPLE_SIZE = 1
MAX_SIMPLE_SIZE = 20

MULT_NESTED_SIZE = 10
MIN_NESTED_SIZE = 1
MAX_NESTED_SIZE = 20

MULT_DEEP_SIZE = 1
MIN_DEEP_SIZE = 10
MAX_DEEP_SIZE = 30

MULT_RUN = 3

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

    def bench(self, implementation_name, benchmark_name, url, size):
        data = []
        for _ in xrange(MULT_RUN):
            # take the average over MULT_RUN runs
            start = datetime.now()
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            end = datetime.now()
            diff = end - start
            data.append(diff.total_seconds())

        self._results[benchmark_name][implementation_name][size] = (
            sum(data) / MULT_RUN
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
        for size in range(MIN_SIMPLE_SIZE, MAX_SIMPLE_SIZE + 1):
            size *= MULT_SIMPLE_SIZE
            self.generate_simple(size)
            self.bench('DREST', 'Simple', '/drest/users/', size)
            self.bench('DRF', 'Simple', '/drf/users/', size)

    def test_nested(self):
        for size in range(MIN_NESTED_SIZE, MAX_NESTED_SIZE + 1):
            size *= MULT_NESTED_SIZE
            self.generate_nested(size)
            self.bench(
                'DREST',
                'Nested',
                '/drest/users/?include[]=groups.',
                size
            )
            self.bench(
                'DRF',
                'Nested',
                '/drf/users_with_groups/',
                size
            )

    def test_deep(self):
        for size in range(MIN_DEEP_SIZE, MAX_DEEP_SIZE + 1):
            size *= MULT_DEEP_SIZE
            self.generate_deep(size)
            self.bench(
                'DREST',
                'Deep',
                '/drest/users/'
                '?include[]=groups.permissions.&include[]=permissions.',
                size
            )
            self.bench(
                'DRF',
                'Deep',
                '/drf/users_with_all/',
                size
            )
