
TEST_REPORT_DIR:=.test-report
TEST_REPORT_FILE:=test-report.xml

setup:
	poetry install -v

setup-all:
	poetry install -v --all-extras

prepare-test:
	rm -rf $(TEST_REPORT_DIR) && mkdir $(TEST_REPORT_DIR)

coverage: prepare-test lint
	poetry run coverage run --rcfile=.coveragerc -m pytest --junitxml $(TEST_REPORT_DIR)/$(TEST_REPORT_FILE)
	poetry run coverage report

lint: setup-all
	poetry run pre-commit run --all

build: setup-all
	poetry build -v

clean:
	rm -rf .coverage dist .pytest_cache $(TEST_REPORT_DIR)

test: setup-all prepare-test
	poetry run pytest --junitxml $(TEST_REPORT_DIR)/$(TEST_REPORT_FILE)