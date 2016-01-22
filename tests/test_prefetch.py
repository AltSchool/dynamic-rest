from django.db.models import Prefetch
from django.test import TestCase

from tests.models import A, B, C, D


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
