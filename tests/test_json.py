import json
from django.test import TestCase
from tests.setup import create_fixture


class TestJSONFieldFiltering(TestCase):

    def setUp(self):
        self.fixture = create_fixture()

    def test_filter_by_first_level(self):
        url = (
            '/recipes/?filter{ingredients.chocolate_chips}=20_g'
        )
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode('utf-8'))

        self.assertTrue('recipes' in content)
        self.assertEqual(2, len(content['recipes']))

        self.assertTrue('name' in content['recipes'][0])
        self.assertEqual(
            'chocolate chip muffin',
            content['recipes'][0]['name']
        )

        self.assertTrue('name' in content['recipes'][1])
        self.assertEqual('chocolate chip scone', content['recipes'][1]['name'])

    def test_filter_by_second_level(self):
        url = (
            '/recipes/?filter{ingredients.dough.water}=50_g'
        )
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode('utf-8'))

        self.assertTrue('recipes' in content)
        self.assertEqual(2, len(content['recipes']))

        self.assertTrue('name' in content['recipes'][0])
        self.assertEqual('scone', content['recipes'][0]['name'])

        self.assertTrue('name' in content['recipes'][1])
        self.assertEqual('chocolate chip scone', content['recipes'][1]['name'])

    def test_filter_by_multiple_criteria(self):
        url = (
            '/recipes/?'
            'filter{ingredients.dough.water}=50_g'
            '&filter{ingredients.chocolate_chips}=20_g'
        )
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode('utf-8'))

        self.assertTrue('recipes' in content)
        self.assertEqual(1, len(content['recipes']))

        self.assertTrue('name' in content['recipes'][0])
        self.assertEqual('chocolate chip scone', content['recipes'][0]['name'])
