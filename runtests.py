#! /usr/bin/env python
# Adopted from Django REST Framework:
# https://github.com/tomchristie/django-rest-framework/blob/master/runtests.py
from __future__ import print_function

import os
import subprocess
import sys

import pytest

APP_NAME = 'dynamic_rest'
TESTS = 'tests'
BENCHMARKS = 'benchmarks'
PYTEST_ARGS = {
    'default': [
        TESTS, '--tb=short', '-s', '-rw'
    ],
    'fast': [
        TESTS, '--tb=short', '-q', '-s', '-rw'
    ],
}

FLAKE8_ARGS = [APP_NAME, TESTS]

sys.path.append(os.path.dirname(__file__))


def exit_on_failure(ret, message=None):
    if ret:
        sys.exit(ret)


def flake8_main(args):
    print('Running flake8 code linting')
    ret = subprocess.call(['flake8'] + args)
    print('flake8 failed' if ret else 'flake8 passed')
    return ret


def split_class_and_function(string):
    class_string, function_string = string.split('.', 1)
    return "%s and %s" % (class_string, function_string)


def is_function(string):
    # `True` if it looks like a test function is included in the string.
    return string.startswith('test_') or '.test_' in string


def is_class(string):
    # `True` if first character is uppercase - assume it's a class name.
    return string[0] == string[0].upper()


if __name__ == "__main__":
    try:
        sys.argv.remove('--nolint')
    except ValueError:
        run_flake8 = True
    else:
        run_flake8 = False

    try:
        sys.argv.remove('--lintonly')
    except ValueError:
        run_tests = True
    else:
        run_tests = False

    try:
        sys.argv.remove('--benchmarks')
    except ValueError:
        run_benchmarks = False
    else:
        run_benchmarks = True

    try:
        sys.argv.remove('--fast')
    except ValueError:
        style = 'default'
    else:
        style = 'fast'
        run_flake8 = False

    if len(sys.argv) > 1:
        pytest_args = sys.argv[1:]
        first_arg = pytest_args[0]

        try:
            pytest_args.remove('--coverage')
        except ValueError:
            pass
        else:
            pytest_args = [
                '--cov-report',
                'xml',
                '--cov',
                APP_NAME
            ] + pytest_args

        if first_arg.startswith('-'):
            # `runtests.py [flags]`
            pytest_args = [TESTS] + pytest_args
        elif is_class(first_arg) and is_function(first_arg):
            # `runtests.py TestCase.test_function [flags]`
            expression = split_class_and_function(first_arg)
            pytest_args = [TESTS, '-k', expression] + pytest_args[1:]
        elif is_class(first_arg) or is_function(first_arg):
            # `runtests.py TestCase [flags]`
            # `runtests.py test_function [flags]`
            pytest_args = [TESTS, '-k', pytest_args[0]] + pytest_args[1:]
    else:
        pytest_args = PYTEST_ARGS[style]

    if run_benchmarks:
        pytest_args[0] = BENCHMARKS
        pytest_args.append('--ds=%s.settings' % BENCHMARKS)

    if run_tests:
        exit_on_failure(pytest.main(pytest_args))

    if run_flake8:
        exit_on_failure(flake8_main(FLAKE8_ARGS))
