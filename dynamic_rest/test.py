from django.test import TestCase


class ViewSetTestCase(TestCase):
    """Base class that makes it easy to test dynamic viewsets.

    You must set the "view" property to an API-bound view.

    This test runs through the various exposed endpoints,
    making internal API calls.

    Default test cases:
        test_list:
            - Only runs if the view allows GET
        test_get
            - Only runs if the view allows GET
        test_create
            - Only runs if the view allows POST
        test_update
            - Only run if the view allows PUT
        test_delete
            - Only run if the view allows DELETE

    Example usage:

        class MyAdminViewSetTestCase(AdminViewSetTestCase):
            viewset = UserViewSet


    """
    viewset = None

    def test_list(self):
        if self.viewset is None:
            return

    def test_get(self):
        if self.viewset is None:
            return

    def test_create(self):
        pass

    def test_update(self):
        pass

    def test_delete(self):
        pass
