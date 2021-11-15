APP_NAME := 'dynamic_rest'
INSTALL_DIR  ?= ./build
PORT         ?= 9002

define header
	@tput setaf 6
	@echo "* $1"
	@tput sgr0
endef

.PHONY: docs

pypi_upload_test: install
	$(call header,"Uploading new version to PyPi - test")
	@. $(INSTALL_DIR)/bin/activate; python setup.py sdist
	@twine upload --repository testpypi dist/*

pypi_upload: install
	$(call header,"Uploading new version to PyPi")
	@. $(INSTALL_DIR)/bin/activate; python setup.py sdist
	@twine upload dist/*

docs: install
	$(call header,"Building docs")
	@DJANGO_SETTINGS_MODULE='tests.settings' $(INSTALL_DIR)/bin/sphinx-build -b html ./docs ./_docs
	@cp -r ./_docs/* ./docs
	@rm -rf ./_docs

# Build/install the app
# Runs on every command
install: $(INSTALL_DIR)
	$(call header,"Installing")
	@$(INSTALL_DIR)/bin/python setup.py -q develop

# Install/update dependencies
# Runs whenever the requirements.txt file changes
$(INSTALL_DIR): $(INSTALL_DIR)/bin/activate
$(INSTALL_DIR)/bin/activate: requirements.txt install_requires.txt
	$(call header,"Updating dependencies")
	@test -d $(INSTALL_DIR) || virtualenv $(INSTALL_DIR)
	@$(INSTALL_DIR)/bin/pip install -q --upgrade pip setuptools flake8==2.4.0
	@$(INSTALL_DIR)/bin/pip install -U -r requirements.txt
	@touch $(INSTALL_DIR)/bin/activate

fixtures: install
	$(call header,"Initializing fixture data")
	$(INSTALL_DIR)/bin/python manage.py migrate --settings=tests.settings
	$(INSTALL_DIR)/bin/python manage.py initialize_fixture --settings=tests.settings

# Removes build files in working directory
clean_working_directory:
	$(call header,"Cleaning working directory")
	@rm -rf ./.tox ./dist ./$(APP_NAME).egg-info;
	@find . -name '*.pyc' -type f -exec rm -rf {} \;

# Full clean
clean: clean_working_directory
	$(call header,"Cleaning all build files")
	@rm -rf $(INSTALL_DIR)

# Run tests
test: install lint
	$(call header,"Running unit tests")
	@$(INSTALL_DIR)/bin/py.test --cov=$(APP_NAME) tests/$(TEST)

# Run tests
integration: install lint
	$(call header,"Running integration tests")
	@ENABLE_INTEGRATION_TESTS=True $(INSTALL_DIR)/bin/py.test tests/integration/$(TEST)

test_just: install lint
	$(call header,"Running unit tests")
	@$(INSTALL_DIR)/bin/py.test --cov=$(APP_NAME) -k $(TEST) --ignore=build --ignore=benchmarks --nomigrations

# Run all tests (tox)
tox: install
	$(call header,"Running multi-version tests")
	@$(INSTALL_DIR)/bin/tox $(CMD)

# Benchmarks
benchmarks: benchmark
benchmark: install
	$(call header,"Running benchmarks")
	@$(INSTALL_DIR)/bin/python runtests.py --benchmarks --fast

# Create test app migrations
migrations: install
	$(call header,"Creating test app migrations")
	$(INSTALL_DIR)/bin/python manage.py makemigrations --settings=tests.settings

# Start the Django shell
shell: install
	$(call header,"Starting shell")
	$(INSTALL_DIR)/bin/python manage.py shell --settings=tests.settings

# Run a Django command
run: install
	$(call header,"Running command: $(CMD)")
	$(INSTALL_DIR)/bin/python manage.py $(CMD) --settings=tests.settings

# Start the development server
serve: server
server: start
start: install
	$(call header,"Starting development server")
	$(INSTALL_DIR)/bin/python manage.py migrate --settings=tests.settings
	$(INSTALL_DIR)/bin/python manage.py runserver $(PORT) --settings=tests.settings

# Lint the project
lint: clean_working_directory
	$(call header,"Linting code")
	@find . -type f -name '*.py' -not -path '$(INSTALL_DIR)/*' -not -path './docs/*' -not -path './env/*' -not -path '$(INSTALL_DIR)/*' | xargs $(INSTALL_DIR)/bin/flake8

# Auto-format the project
format: clean_working_directory
	$(call header,"Auto-formatting code")
	@find $(APP_NAME) -type f -name '*.py' | xargs $(INSTALL_DIR)/bin/flake8 | sed -E 's/^([^:]*\.py).*/\1/g' | uniq | xargs autopep8 --experimental -a --in-place
