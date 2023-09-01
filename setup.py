from setuptools import find_packages, setup

NAME = 'dynamic-rest-bse'
DESCRIPTION = 'Dynamic API support to Django REST Framework. Temp fork for until Django is updated upstream...'
URL = 'http://github.com/BillSchumacher/dynamic-rest'
VERSION = '2.2.1'
SCRIPTS = ['manage.py']

setup(
    description=DESCRIPTION,
    include_package_data=True,
    install_requires=open('install_requires.txt').readlines(),
    long_description=open('README.rst').read(),
    name=NAME,
    packages=find_packages(exclude=["benchmarks", "tests"]),
    scripts=SCRIPTS,
    url=URL,
    version=VERSION,
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
