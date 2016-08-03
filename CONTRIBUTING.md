We encourage bug reports, suggestions for improvements, and direct contributions through Github Issues/Pull Requests.

When making contributions, try to follow these guidelines:

# Development

## Style

Use `make lint` to check your code for style violations.

We use the `flake8` linter to enforce PEP8 code style. 
For additional details, see our [Python style guide](https://github.com/AltSchool/Python).

## Documentation

Use `make docs` to generate the automated documentation for the project.

We recommend documenting all public modules, classes, and methods, but generating the documentation is not required.

## Tests

Use `make test` to lint and run all unit tests (runs in a few seconds).
Use `make tox` to run all unit tests against all supported combinations of Python, Django, and Django REST Framework (can take several minutes).

We recommend linting regularly, testing with every commit, and running tests against all combinations before submitting a pull request.

## Benchmarks

Use `make benchmark` to benchmark your changes against the latest version of Django REST Framework (can take several minutes).

We recommend running this before submitting a pull request. Doing so will create a [benchmarks.html](benchmarks.html) file in the repository root directory.

# Submission

Please submit your pull request with a clear title and description.
Any visual changes (e.g. to the Browsable API) should include screenshots in the description.
Any related issues in Dynamic REST, Django REST Framework, or Django should include a URL reference to the issue.

# Publishing

(PyPi and repository write access required)

Before releasing:

- Check/update the version in `dynamic_rest/constants.py`
- Commit changes and tag the commit with the version, prefixed by "v"
- Run `make pypi_upload_test` to upload a new version to PyPiTest. Check the contents at https://pypitest.python.org/pypi/dynamic-rest
- Run `make pypi_upload` to upload a new version to PyPi. Check the contents at https://pypi.python.org/pypi/dynamic-rest
