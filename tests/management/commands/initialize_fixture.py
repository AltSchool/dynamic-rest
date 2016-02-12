from django.core.management.base import BaseCommand

from tests.setup import create_fixture


class Command(BaseCommand):
    help = 'Loads fixture data'

    def handle(self, *args, **options):
        create_fixture()

        self.stdout.write("Loaded fixtures.")
