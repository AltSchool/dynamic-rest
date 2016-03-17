import json

from rest_framework.test import APITestCase

from tests.setup import create_fixture


class TestContentTypeFieldAPI(APITestCase):

    def setUp(self):
        self.fixture = create_fixture()
        f = self.fixture
        f.users[0].favorite_pet = f.cats[0]
        f.users[0].save()

        f.users[1].favorite_pet = f.cats[1]
        f.users[1].save()

        f.users[2].favorite_pet = f.dogs[1]
        f.users[2].save()

    def test_basic(self):
        url = (
            '/users/?include[]=favorite_pet.'
            '&filter{favorite_pet_id.isnull}=false'
        )
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        content = json.loads(response.content.decode('utf-8'))
        self.assertTrue(
            all(
                [_['favorite_pet'] for _ in content['users']]
            )
        )
        self.assertTrue('cats' in content)
        self.assertEqual(2, len(content['cats']))
        self.assertTrue('dogs' in content)
        self.assertEqual(1, len(content['dogs']))

    def test_query_counts(self):
        # NOTE: Django doesn't seem to prefetch ContentType objects
        #       themselves, and rather caches internally. That means
        #       this call could do 5 SQL queries if the Cat and Dog
        #       ContentType objects haven't been cached.
        with self.assertNumQueries(3):
            url = (
                '/users/?include[]=favorite_pet.'
                '&filter{favorite_pet_id.isnull}=false'
            )
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)

        with self.assertNumQueries(3):
            url = '/users/?include[]=favorite_pet.'
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)
