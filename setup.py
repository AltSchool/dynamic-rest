import sys
from setuptools import find_packages, setup

NAME = 'dynamic-rest'
DESCRIPTION = 'Adds Dynamic API support to Django REST Framework.'
URL = 'http://github.com/AltSchool/dynamic-rest'
VERSION = '1.9.5'
SCRIPTS = ['manage.py']

setup(
    description=DESCRIPTION,
    include_package_data=True,
    install_requires=open('install_requires.txt'
                          if sys.version_info.major == 2
                          else 'install_requires_python3.txt').readlines(),
    long_description=open('README.rst').read(),
    name=NAME,
    packages=find_packages(),
    scripts=SCRIPTS,
    url=URL,
    version=VERSION
)
