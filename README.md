# SenseiAPI

A FastAPI service (Python 3.11+).

## Requirements

- Python 3.11+
- `pip` and `venv`
- Docker Desktop or Docker Engine with Docker Compose

## Setup

```bash
# Create and activate a virtual environment
python -m venv .venv
conda deactivate 2>/dev/null || true   # avoid conda shadowing .venv/bin (see Troubleshooting)
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install runtime + dev dependencies
pip install -r requirements-dev.txt

# Create local environment config
cp .env.example .env
```

> `requirements-dev.txt` includes everything in `requirements.txt` plus the test/lint tools.
> For a production install, use `pip install -r requirements.txt`.

## Transcription

Speech-to-text runs through one of two backends, chosen by `TRANSCRIBER_BACKEND`:

| Backend | Value | Notes |
| --- | --- | --- |
| ElevenLabs Scribe | `elevenlabs` (default) | Hosted API. Needs `ELEVENLABS_API_KEY`; billed per minute of audio. |
| Local Whisper | `whisper` | Runs `faster-whisper` in-process. Free and offline, slower on CPU. |

Both return the same shape — text, detected language, and word-level timestamps —
so switching backends never changes the API response.

Startup fails if `TRANSCRIBER_BACKEND=elevenlabs` and no API key is set, rather
than silently downgrading to Whisper.

## Local database

Start PostgreSQL with Docker Compose:

```bash
docker compose up -d db
```

Run psql from inside docker container:

```
# Get container id
docker ps

# Run shell inside the container
docker exec -it <container_id> bash

# Run psql
psql -U sensei -d senseiapi
```

Stop the database:

```bash
docker compose down
```

Remove local PostgreSQL data:

```bash
rm -rf .docker/postgres_data
```

## Run the server

```bash
docker compose up -d db
export ENABLE_SECURITY=true  # enable/disable authentication
uvicorn main:app --reload
```

The API is then available at:

- App root: http://127.0.0.1:8000/
- Health check: http://127.0.0.1:8000/health
- Readiness check: http://127.0.0.1:8000/ready
- Interactive docs (Swagger UI): http://127.0.0.1:8000/docs
- Alternative docs (ReDoc): http://127.0.0.1:8000/redoc

## Quality checks

Use the project virtualenv (conda/base Python does not have API dependencies).
Either activate it first, or use the Makefile (recommended):

```bash
make check              # lint + format + mypy + unit tests
make test               # unit tests only
make test-all           # unit + integration (needs Docker)
```

Or manually after `source .venv/bin/activate` (and `conda deactivate` if you use Anaconda):

```bash
ruff check .            # lint
ruff format --check .   # formatting
mypy .                  # static type checks
python -m pytest -m "not integration"   # unit tests (prefer over bare `pytest`)
```

### Troubleshooting tests

If `pytest` fails with `ModuleNotFoundError` for packages you already installed:

1. **Conda is shadowing the venv** — your prompt may show `(base)` and `(.venv)` together. Run `conda deactivate`, then `source .venv/bin/activate`, and confirm `which python` points at `senseiapi/.venv/bin/python`.
2. **Use the venv interpreter explicitly** — `python -m pytest` or `make test` always use the right Python.
3. **Venv was moved or copied** — reinstall CLI entry points: `pip install --force-reinstall -r requirements-dev.txt`.

Auto-fix what's fixable:

```bash
ruff check --fix .
ruff format .
```

## Testing

Yes — the API has a full test suite (168 tests: 154 unit, 14 integration). It covers auth, patients, calendar, audio/transcription, summaries, reports, and DB wiring. CI runs these; you should run unit tests before PRs.

- Tests live in `tests/` and are named `test_*.py`.
- Run with `make test` or `python -m pytest` (not bare `pytest` when conda is active).
- Endpoints are tested via `fastapi.testclient.TestClient`; assert both status code and response body.
- Database integration tests use Testcontainers and require Docker.
- Run `pytest -m "not integration"` to skip integration tests.
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
