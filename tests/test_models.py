from django.test import TestCase
from django.db.models import Prefetch
from tests.models import A, B, C, D


class TestModels(TestCase):

    def testNestedPrefetch(self):
        a = A.objects.create(name="a")
        b = B.objects.create(a=a)
        d = D.objects.create(name="d")
        c = C.objects.create(b=b, a=a, d=d)

        a = A.objects.filter(pk=a.pk).prefetch_related(
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
