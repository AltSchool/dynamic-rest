from setuptools import find_packages, setup

NAME = 'dynamic-rest'
DESCRIPTION = 'Dynamic API support to Django REST Framework.'
URL = 'https://github.com/cesar-benjamin/drf-dynamic-rest'
VERSION = "2023.11-alpha7"
SCRIPTS = ['manage.py']

setup(
    description=DESCRIPTION,
    install_requires=open('install_requires.txt').readlines(),
    long_description=open('README.rst').read(),
    name=NAME,
    package_dir={"": "src"},
    packages=find_packages("src"),
    scripts=SCRIPTS,
    url=URL,
    version=VERSION,
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.10',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
