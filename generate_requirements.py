"""This script will generate a requirements.txt file from the Pipfile."""
#  Copyright (c) 2023. Bill Schumacher
#   All Rights Reserved, confidential.
import os

os.system("pipenv requirements > config/requirements.txt")
