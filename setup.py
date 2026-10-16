"""Setup script for dynamic-rest-bse."""

from setuptools import find_packages, setup

NAME = "dynamic-rest-bse"
DESCRIPTION = "Dynamic API support to Django REST Framework. Forked..."
URL = "http://github.com/BillSchumacher/dynamic-rest"
VERSION = "2.5.5"
with open("install_requires.txt", encoding="utf-8") as fp:
    INSTALL_REQUIRES = [line.strip() for line in fp if line.strip()]

with open("README.rst", encoding="utf-8") as fp:
    LONG_DESCRIPTION = fp.read()

setup(
    description=DESCRIPTION,
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/x-rst",
    name=NAME,
    packages=find_packages(exclude=["benchmarks", "tests"]),
    python_requires=">=3.9",
    url=URL,
    version=VERSION,
    classifiers=[
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
