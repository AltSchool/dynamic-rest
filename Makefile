QUOTE := [\"]
WORD := [A-Z_]+
WHITESPACE := [ ]*
EXTRACT_REGEX := 's~^$(WHITESPACE)$(WORD)$(WHITESPACE)=$(WHITESPACE)$(QUOTE)(.*)$(QUOTE)$$~\1~'
ORG_NAME := $(shell grep ORG_NAME constants.py | sed -E $(EXTRACT_REGEX))
REPO_NAME := $(shell grep REPO_NAME constants.py | sed -E $(EXTRACT_REGEX))
APP_NAME := $(shell grep APP_NAME constants.py | sed -E $(EXTRACT_REGEX))
PROJECT_NAME := $(shell grep PROJECT_NAME constants.py | sed -E $(EXTRACT_REGEX))
AUTHOR_EMAIL := $(shell grep AUTHOR_EMAIL constants.py | sed -E $(EXTRACT_REGEX))
VERSION := $(shell grep VERSION constants.py | sed -E $(EXTRACT_REGEX))

INSTALL_PREFIX := /usr/local
INSTALL_DIR  := $(INSTALL_PREFIX)/$(ORG_NAME)/$(REPO_NAME)
PORT         ?= 9001

define header
	@tput setaf 6
	@echo "* $1"
	@tput sgr0
endef

.PHONY: docs

docs: install
	$(call header,"Building docs")
	@rm -rf ./docs
	@$(INSTALL_DIR)/bin/sphinx-apidoc -F -o ./docs $(APP_NAME) -H "$(PROJECT_NAME)" -A "$(AUTHOR_EMAIL)" -V $(VERSION) -R $(VERSION)
	@sed -i -E "s/sphinx.ext.autodoc'/sphinx.ext.autodoc', 'sphinx.ext.napoleon'/" ./docs/conf.py
	@rm -rf ./docs/conf.py-E
	@DJANGO_SETTINGS_MODULE='tests.settings' $(INSTALL_DIR)/bin/sphinx-build -b html ./docs ./_docs
	@cp -r ./_docs/* ./docs
	@rm -rf ./_docs

# Build/install the app
# Runs on every command
install: $(INSTALL_DIR)
	$(call header,"Installing")
	@$(INSTALL_DIR)/bin/python setup.py -q install

# Install/update dependencies
# Runs whenever the requirements.txt file changes
$(INSTALL_DIR): $(INSTALL_DIR)/bin/activate
$(INSTALL_DIR)/bin/activate: requirements.txt install_requires.txt dependency_links.txt
	$(call header,"Updating dependencies")
	@test -d $(INSTALL_DIR) || virtualenv $(INSTALL_DIR)
	@$(INSTALL_DIR)/bin/pip install -q --upgrade pip
	@$(INSTALL_DIR)/bin/pip install --process-dependency-links -Ur requirements.txt
	@touch $(INSTALL_DIR)/bin/activate

# Removes build files in working directory
clean_working_directory:
	$(call header,"Cleaning working directory")
	@rm -rf ./.tox ./build ./dist ./$(APP_NAME).egg-info;
	@find . -name '*.pyc' -type f | xargs rm

# Full clean
clean: clean_working_directory
	$(call header,"Cleaning all build files")
	@rm -rf $(INSTALL_DIR)

# Run tests
test: lint install
	$(call header,"Running unit tests")
	@$(INSTALL_DIR)/bin/py.test --cov=$(APP_NAME) --tb=short -q -s -rw tests/$(TEST)

# Run all tests (tox)
tox: lint install
	$(call header,"Running multi-version tests")
	@$(INSTALL_DIR)/bin/tox

# Benchmarks
bench: install
	$(call header,"Running benchmarks")
	@$(INSTALL_DIR)/bin/python runtests.py --benchmarks --fast

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
	@find . -type f -name '*.py' | xargs flake8

# Auto-format the project
format: clean_working_directory
	$(call header,"Auto-formatting code")
	@find $(APP_NAME) -type f -name '*.py' | xargs flake8 | sed -E 's/^([^:]*\.py).*/\1/g' | uniq | xargs autopep8 --experimental -a --in-place
