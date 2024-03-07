"""Blueprint context for dynamic_rest."""
import click


@click.command()
def get_context():
    """Get context for a blueprint."""
    return {}
