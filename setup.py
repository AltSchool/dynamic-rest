from setuptools import find_packages, setup

from dynamic_rest.constants import (
    AUTHOR,
    AUTHOR_EMAIL,
    DESCRIPTION,
    ORG_NAME,
    REPO_NAME,
    VERSION
)

EXCLUDE_FROM_PACKAGES = []

setup(
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    description=DESCRIPTION,
    include_package_data=True,
    dependency_links=open('dependency_links.txt').readlines(),
    install_requires=open('install_requires.txt').readlines(),
    long_description=open('README.rst').read(),
    name=REPO_NAME,
    packages=find_packages(exclude=EXCLUDE_FROM_PACKAGES),
    scripts=['manage.py'],
    url='http://github.com/%s/%s' % (ORG_NAME, REPO_NAME),
    version=VERSION,
)
