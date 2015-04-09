INSTALL_DIR  := /usr/local/dynamic-rest

.PHONY: test

install: $(INSTALL_DIR)
	. $(INSTALL_DIR)/bin/activate; python setup.py install

$(INSTALL_DIR): $(INSTALL_DIR)/bin/activate
$(INSTALL_DIR)/bin/activate: requirements.txt
	test -d $(INSTALL_DIR) || virtualenv $(INSTALL_DIR)
	. $(INSTALL_DIR)/bin/activate; pip install -U -r requirements.txt
	touch $(INSTALL_DIR)/bin/activate

clean:
	rm -rf $(INSTALL_DIR)

test: install
	. $(INSTALL_DIR)/bin/activate; \
	  python manage.py test --settings=tests.settings

run: install
	. $(INSTALL_DIR)/bin/activate; \
	  python manage.py $(CMD) --settings=tests.settings

coverage: install
	. $(INSTALL_DIR)/bin/activate; \
    coverage run --source='.' manage.py test --settings=tests.settings; coverage report

server: install
	. $(INSTALL_DIR)/bin/activate; \
	  python manage.py migrate --settings=tests.settings; \
    python manage.py runserver --settings=tests.settings

