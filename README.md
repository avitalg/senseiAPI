# SenseiAPI

A FastAPI service (Python 3.11+).

## Requirements

- Python 3.11+
- `pip` and `venv`

## Setup

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install runtime + dev dependencies
pip install -r requirements-dev.txt
```

> `requirements-dev.txt` includes everything in `requirements.txt` plus the test/lint tools.
> For a production install, use `pip install -r requirements.txt`.

## Run the server

```bash
uvicorn main:app --reload
```

The API is then available at:

- App root: http://127.0.0.1:8000/
- Health check: http://127.0.0.1:8000/health
- Interactive docs (Swagger UI): http://127.0.0.1:8000/docs
- Alternative docs (ReDoc): http://127.0.0.1:8000/redoc

## Quality checks

Run all of these before opening a PR or marking a task done — they must all pass:

```bash
ruff check .            # lint
ruff format --check .   # formatting
mypy .                  # static type checks
pytest                  # tests
```

Auto-fix what's fixable:

```bash
ruff check --fix .
ruff format .
```

## Testing

- Tests live in `tests/` and are named `test_*.py`.
- Run the suite with `pytest` (or `pytest -q` for quiet output).
- Endpoints are tested via `fastapi.testclient.TestClient`; assert both status code and response body.
- Cover the happy path, edge cases, and failure paths.

## Project structure

```
senseiapi/
├── main.py               # FastAPI app + entry point
├── tests/                # Pytest test suite
├── requirements.txt      # Runtime dependencies
├── requirements-dev.txt  # Dev/test dependencies (includes runtime)
├── pyproject.toml        # ruff, mypy, and pytest configuration
├── AGENTS.md             # Guide for AI coding agents (Claude, Cursor, etc.)
└── .cursor/rules/        # Cursor coding-standard rules
```

## Coding standards

Conventions for this project (types, FastAPI patterns, testing, error handling)
are documented in `AGENTS.md` and enforced via `.cursor/rules/`. Please read
`AGENTS.md` before contributing.
