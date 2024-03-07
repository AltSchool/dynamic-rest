"""This script will generate a requirements.txt file from the Pipfile."""
import os

os.system("pipenv requirements > config/requirements.txt")
