VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Default: full verification before merge/push (lint, format, types, all tests).
.DEFAULT_GOAL := check-all

.PHONY: install test test-all lint format format-check typecheck check check-all

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

# Fast local gate: lint + format + types + unit tests (no Docker).
check: lint format-check typecheck test

# Full gate: lint + format + types + unit + integration (needs Docker).
check-all: lint format-check typecheck test-all
