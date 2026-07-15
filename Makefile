VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: install test test-all lint format format-check typecheck check

install:
	test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install -r requirements-dev.txt

test: install
	$(PYTHON) -m pytest -m "not integration"

test-all: install
	$(PYTHON) -m pytest

lint: install
	$(VENV)/bin/ruff check .

format: install
	$(VENV)/bin/ruff format .

format-check: install
	$(VENV)/bin/ruff format --check .

typecheck: install
	$(PYTHON) -m mypy .

check: lint format-check typecheck test
