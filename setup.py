from distutils.core import setup
import codecs
import os
import re

PACKAGE_NAME = 'dynamic_rest'
BASE_DIR = os.path.dirname(__file__) or "."
VERSION = re.search('__version__ = "([^"]+)"',
                    codecs.open("%s/%s/__init__.py" % (BASE_DIR, PACKAGE_NAME), encoding='utf-8').read()).group(1)

setup(
    author="Anthony Leontiev",
    author_email="ant@altschool.com",
    description="Dynamic extensions for Django REST Framework",
    long_description=open("README.md").read(),
    name=PACKAGE_NAME,
    packages=[
        PACKAGE_NAME,
        "tests",
    ],
    scripts=['manage.py'],
    url="http://github.com/AltSchool/dynamic-rest",
    version=VERSION,
    test_suite='runtests.runtests'
)
