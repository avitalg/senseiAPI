# SenseiAPI — Agent Guide

Instructions for AI coding agents (Claude, Cursor, etc.). Follow these on every change.
Cursor users: the same rules live in `.cursor/rules/` and apply automatically.

## Project
- FastAPI service (Python 3.11+). Entry point: `main.py`.
- Dependencies in `requirements.txt`; dev/test tools in `requirements-dev.txt`.
- Transcription has two interchangeable backends behind the `Transcriber` ABC, picked by
  `TRANSCRIBER_BACKEND`: `elevenlabs` (default, hosted, needs `ELEVENLABS_API_KEY`) and
  `whisper` (local `faster-whisper`). Both must return the same `Transcript` shape.
  Never let tests hit the real ElevenLabs API — inject a fake client.
- Session summaries and next-meeting prep reports share backends behind
  `Summarizer` / `ReportSynthesizer`, picked by `SUMMARY_BACKEND`: `ollama`
  (default, local PHI-safe) and `openai` (hosted; needs `OPENAI_API_KEY`, reuses
  `OPENAI_MODEL`). Never let tests hit the real Ollama/OpenAI APIs — inject a
  fake client.
- Chat assistant (`assistant/`): `POST /assistant/chat` runs a streaming tool-call loop
  and emits a **Vercel AI-SDK "UI message stream"** (SSE) — text + tool-input/tool-output
  parts — that the Sensei frontend consumes with `useChat`. Hosted OpenAI Python SDK
  (`openai`); config `OPENAI_API_KEY` / `OPENAI_MODEL` (default `gpt-4o`) /
  `ASSISTANT_ENABLED` / `ASSISTANT_SELF_BASE_URL`; returns 503 until configured.
  **Observability (`assistant/tracing.py`, off by default):** set `LANGFUSE_ENABLED=true`
  + `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_BASE_URL` to trace each chat as
  one Langfuse trace (model rounds + tool calls nested, tagged with the therapist
  `user_id` + conversation `session_id`). Behind a `Tracer` seam — `NoOpTracer` default
  imports no `langfuse`; enabled uses the `langfuse.openai` drop-in. The
  system prompt (`assistant/prompt.py`) is trauma-informed and clinician-facing (see
  `docs/research/`). Tools (`assistant/tools.py`): `discover_api` reads the **live
  OpenAPI** (`GET /openapi.json`) — endpoints are discovered, never hardcoded; `http_get`
  is GET-only, same-host (SSRF/traversal guards always on). Scope set by
  `ASSISTANT_ALLOW_ALL_GETS`: **false (default, PHI-safe)** = confined to
  `/assistant/context/*` (`assistant/context.py`: roster / agenda / per-patient cadence /
  per-patient **meetings** — the meeting_id + `has_summary` chain to a session summary;
  name+schedule only, timestamps pre-formatted numeric `DD/MM/YYYY HH:MM` via `_readable`,
  never free-text titles); **true (demo)** = any GET on this API, incl. PHI — flip to false
  for real deployments. `assistant/prompt.py` carries **playbooks** mapping each question
  type to its GET chain. Never let tests hit the real OpenAI API or network — inject fake
  `AssistantClient` / fake `Fetcher`.
  The assistant answers over the canonical demo data seeded by `seeds/` (per-patient
  JSON with sessions + ready summaries), loaded on startup when `SEED_ON_STARTUP=true`.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

## Run & Verify
- Run the API: `uvicorn main:app --reload`
- Before declaring any task done, ALL of these must pass:
  - `ruff check .`
  - `ruff format --check .`
  - `mypy .`
  - `pytest`
- GitHub Actions (`.github/workflows/ci.yml`) runs the same full gate (`make check-all`)
  on every PR and push to `main`; keep that workflow green before merge/deploy.

## Coding Standards (must follow)
- **Types everywhere.** Full type hints on all functions; no bare `Any` without a reason.
- **Thin handlers.** Route handlers validate input and delegate to services/functions; keep business logic out of the handler.
- **Pydantic at the boundary.** Validate all external input; use explicit request/response models and `response_model=`. Never return secrets or raw ORM objects.
- **Explicit errors.** Catch the narrowest exception, add context, re-raise with `from`. Never `except: pass`. Use `logging`, never `print`. Never log secrets/PII.
- **Config from env.** No hardcoded secrets, URLs, or keys. Keep `.env` out of git.
- **Async-safe.** Use `async def` handlers; never block the event loop with sync I/O.

## Testing (required, not optional)
- Every behavior change ships with `pytest` tests in `tests/` (`test_*.py`).
- Test endpoints via `TestClient`/`httpx.AsyncClient`; assert status code AND body.
- Cover happy path, edge case, and failure path. Use fixtures and `parametrize`.
- Tests must be deterministic and isolated — mock external services, no real network.
- Fixing a bug? Add a failing test that reproduces it first, then fix.
- Never weaken or delete a test just to make the suite green.

## Don'ts
- Don't commit generated artifacts, `.venv`, `.env`, or secrets.
- Don't introduce dependencies without adding them to the requirements files.
- Don't disable lint/type/test checks to "make it pass."
