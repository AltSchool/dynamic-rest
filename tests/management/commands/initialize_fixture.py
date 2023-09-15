"""Initialize fixture data."""
from django.core.management.base import BaseCommand

from tests.setup import create_fixture


class Command(BaseCommand):
    """Initialize fixture data."""

    help = "Loads fixture data"

    def handle(self, *args, **options):
        """Handle the command."""
        create_fixture()

        self.stdout.write("Loaded fixtures.")
