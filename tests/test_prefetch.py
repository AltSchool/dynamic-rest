from django.db.models import Prefetch
from django.test import TestCase

from tests.models import (
    A,
    B,
    C,
    D,
    Location,
    User
)
from tests.setup import create_fixture


class TestPrefetch(TestCase):
    """Tests prefetch corner-case bugs introduced in Django 1.7

    See dynamic_rest.patches for details.
    """

    def test_nested_prefetch(self):
        a = A.objects.create(name="a")
        b = B.objects.create(a=a)
        d = D.objects.create(name="d")
        C.objects.create(b=b, d=d)

        # This fails
        A.objects.prefetch_related(
            Prefetch(
                'b',
                queryset=B.objects.prefetch_related(
                    Prefetch(
                        'cs',
                        queryset=C.objects.prefetch_related(
                            Prefetch(
                                'd',
                                queryset=D.objects.all()
                            )
                        )
                    )
                )
            )
        )[0]

    def test_recursive_prefetch_query_bug(self):
        """Test for presence of Django bug that causes extra queries when
        prefetch tree is recursive:
        i.e. A prefetches B prefetches A prefetches C
        """

        self.fixtures = create_fixture()

        locations = list(Location.objects.prefetch_related(
            Prefetch(
                'user_set',
                User.objects.prefetch_related(
                    Prefetch(
                        'location',
                        Location.objects.prefetch_related('cat_set')
                    )
                )
            )
        ))

        users = list(locations[0].user_set.all())

        # NOTE: this is a bug. All the data should be prefetched, but this
        #       will cause 2 queries to be executed
        with self.assertNumQueries(2):
            for user in users:
                cats = list(user.location.cat_set.all())  # noqa
