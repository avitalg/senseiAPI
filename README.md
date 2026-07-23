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
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install runtime + dev dependencies
pip install -r requirements-dev.txt

# Create local environment config
cp .env.example .env
```

> `requirements-dev.txt` includes everything in `requirements.txt` plus the test/lint tools.
> For a production install, use `pip install -r requirements.txt`.

## Terminology

A **meeting** is a scheduled therapy session. It is stored as a row in the
`calendar_events` table. Throughout the API:

- `meeting_id` on summaries, transcripts, prep reports, and audio upload =
  `calendar_events.id`
- `/calendar/{meeting_id}` manages the schedule; `/meetings/{meeting_id}/summary`
  and related routes attach session artifacts to the same id

The `/calendar` URL prefix and `calendar_events` table name are legacy; new code
should prefer **meeting** in parameter and field names.

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

## Session summaries

Session summaries, next-meeting prep reports, and daily meeting reports share
`SUMMARY_BACKEND`:

| Backend | Value | Notes |
| --- | --- | --- |
| Ollama (local) | `ollama` (default) | PHI stays on-host. Needs a running Ollama + `OLLAMA_MODEL` pulled. |
| OpenAI | `openai` | Hosted Chat Completions. Needs `OPENAI_API_KEY`; reuses `OPENAI_MODEL`. Transcripts / summary text leave the host. |

Both paths use their respective system prompts and normalize model output the same way.
Startup fails if `SUMMARY_BACKEND=openai` and no API key/model is set.

## TTS example

Fill the ElevenLabs placeholders in [`tests/test_tts_example.py`](tests/test_tts_example.py), then
run `pytest -m manual --log-cli-level=INFO tests/test_tts_example.py`. The test prints the full path
to a playable MP3 under `artifacts/`. Do not commit credentials.

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
make                    # default — full verification (see check-all below)
make check-all          # lint + format + mypy + all tests (unit + integration; needs Docker)
make check              # lint + format + mypy + unit tests only (faster, no Docker)
make test               # unit tests only
make test-all           # unit + integration tests only (needs Docker)
```

**Before opening a PR or pushing**, run `make` (or `make check-all`) from `senseiapi/`.
That is the project's default testing target: ruff lint, format check, mypy, and the
full pytest suite including integration tests.

The same gate runs in GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml))
on every pull request and every push to `main`. Mark the `ci / verify` check as
**required** on `main` so nothing deploys from a red build.

Or manually after `source .venv/bin/activate` (and `conda deactivate` if you use Anaconda):

```bash
ruff check .            # lint
ruff format --check .   # formatting
mypy .                  # static type checks
python -m pytest -m "not integration"   # unit tests (prefer over bare `pytest`)
```

Auto-fix what's fixable:

```bash
ruff check --fix .
ruff format .
```

## Testing

- Tests live in `tests/` and are named `test_*.py`.
- Default verification: `make` from `senseiapi/` (runs lint, format check, mypy, and all tests).
- Run the suite with `pytest` (or `pytest -q` for quiet output).
- Endpoints are tested via `fastapi.testclient.TestClient`; assert both status code and response body.
- Database integration tests use Testcontainers and require Docker.
- Run `pytest -m "not integration"` to skip integration tests.
- Cover the happy path, edge cases, and failure paths.

## Database migrations

Schema is created via SQLAlchemy `create_all` on startup, which does **not** alter existing tables.
On startup, [`core/database.py`](core/database.py) also auto-migrates a legacy
`next_meeting_reports` table (adds `meeting_id` when missing). If you need to run
it manually (e.g. before upgrading the API), use:

```sql
-- Drop legacy rows that cannot be mapped to a meeting (optional in dev)
DELETE FROM next_meeting_reports;

ALTER TABLE next_meeting_reports
  ADD COLUMN IF NOT EXISTS meeting_id UUID REFERENCES calendar_events(id) ON DELETE CASCADE;

ALTER TABLE next_meeting_reports DROP CONSTRAINT IF EXISTS next_meeting_reports_patient_id_key;
ALTER TABLE next_meeting_reports DROP CONSTRAINT IF EXISTS next_meeting_reports_meeting_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS ix_next_meeting_reports_meeting_id
  ON next_meeting_reports(meeting_id);
CREATE INDEX IF NOT EXISTS ix_next_meeting_reports_patient_id
  ON next_meeting_reports(patient_id);

ALTER TABLE next_meeting_reports ALTER COLUMN meeting_id SET NOT NULL;
```

Fresh environments get the correct schema automatically from [`reports/orm.py`](reports/orm.py).

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
