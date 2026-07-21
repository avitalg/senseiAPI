# Plan — Add Langfuse observability to the assistant

- **Date:** 2026-07-20
- **Repo:** senseiAPI (FastAPI, Python)
- **Branch:** `feat/assistant-langfuse` (off `avitalg/main`, which contains the
  assistant module via PR #16). Single side branch → one PR (Strategy A).
- **Feature:** trace the "שאל את סנסיי" assistant chat with
  [Langfuse](https://langfuse.com) (LLM observability) — **Langfuse Cloud**.
- **Scope chosen:** drop-in OpenAI tracing **+ per-request trace grouping**
  (each chat request is one trace tagged with the authenticated therapist
  `user_id` and the conversation `session_id`; the multi-round tool-call
  generations nest under it).

## Goal / success criteria

1. With Langfuse **disabled** (default), behaviour is byte-for-byte unchanged —
   no new required env, no import of `langfuse` at request time, all existing
   tests green. (Preserves the client-only / no-key default.)
2. With Langfuse **enabled** (`LANGFUSE_TRACING_ENABLED=true` + keys), every
   `POST /assistant/chat` produces **one Langfuse trace** named `assistant-chat`
   with:
   - `user_id` = authenticated therapist id, `session_id` = conversation id,
   - one **generation** per model round (model, input, output, token usage,
     latency, cost, errors) nested under the trace,
   - the tool calls visible in the trace,
   - the final answer captured as the trace output,
   - errors recorded on the span (level=ERROR) without breaking the SSE stream.
3. Secrets never leak: keys are env-only; the generic `AssistantError` surface to
   the client is unchanged.

## Design

Keep the assistant module **langfuse-agnostic** via a tiny injected abstraction,
mirroring the existing `AssistantClient` ABC / `OpenAIChatClient` Protocol style.

- **`assistant/tracing.py` (new)**
  - `ChatTrace` — small handle with `set_output(text: str)` / `set_error(msg)`.
  - `Tracer` ABC: `trace_chat(*, user_id, session_id) -> AbstractContextManager[ChatTrace]`.
  - `NoOpTracer` — default; the `with` block yields a no-op handle. Zero deps.
  - `LangfuseTracer` — opens `langfuse.start_as_current_observation(name="assistant-chat")`
    and, inside, `propagate_attributes(user_id=..., session_id=..., trace_name="assistant-chat", tags=["assistant"])`;
    `set_output` updates the span output; `set_error` sets level=ERROR + status message.
  - `get_langfuse()` — `@lru_cache` singleton (`Langfuse()` reads env).
  - `build_tracer(settings)` — returns `LangfuseTracer` when enabled + keys present, else `NoOpTracer`.
- **OpenAI drop-in:** in `dependencies.py`, when Langfuse is enabled use
  `from langfuse.openai import AsyncOpenAI`; otherwise the current
  `from openai import AsyncOpenAI`. The drop-in auto-creates the nested generations.
- **Service:** `AssistantService.__init__` gains `tracer: Tracer = NoOpTracer()`.
  `stream_sse(request, *, user_id=None, session_id=None)` wraps the existing
  streaming loop in `with self._tracer.trace_chat(...)`, accumulates the streamed
  text, and calls `trace.set_output(...)` at the end (and `set_error` on
  `AssistantError`). No change to the SSE frames emitted.
- **Router:** add `current_user: User = Depends(get_current_user)` (FastAPI dedups
  the app-level dependency) and pass `user_id=str(current_user.user_id)`,
  `session_id=session_id(request)` into `stream_sse`.
- **Schema:** add optional top-level `id` to `ChatRequest` (useChat sends it) +
  `session_id(request)` helper. Best-effort; `None` when absent.
- **Config:** `langfuse_enabled`, `langfuse_public_key`, `langfuse_secret_key`,
  `langfuse_host` (default `https://cloud.langfuse.com`). Startup validation: if
  enabled, both keys required (mirrors the TTS validation pattern).
- **Streamed token usage:** the Langfuse OpenAI drop-in requests usage on streams.
  Verify usage shows on traces; **only if missing**, add
  `stream_options={"include_usage": True}` to the `create(...)` kwargs in
  `client.py` (the loop already skips empty-`choices` chunks, so it is safe). Kept
  out of the default plan to stay surgical.

## Files

| File | Change |
|---|---|
| `requirements.txt` | add `langfuse>=3.0.0` |
| `core/config.py` | 4 settings + startup validation |
| `assistant/tracing.py` | **new** — Tracer ABC, NoOp, Langfuse impl, factory |
| `assistant/schemas.py` | optional `id` field + `session_id()` helper |
| `assistant/service.py` | inject tracer; wrap stream; capture output/error |
| `assistant/dependencies.py` | pick drop-in client; build + inject tracer |
| `assistant/router.py` | inject current user; pass user_id/session_id |
| `.env.example` | LANGFUSE_* vars, commented, disabled by default |
| `AGENTS.md` / root docs | one-line note on the new env + feature |

## Milestones (both on `feat/assistant-langfuse`, one PR)

### M1 — Core tracing (drop-in) + config
Steps: requirements; config settings + validation; `tracing.py`
(NoOp+Langfuse+factory); dependencies picks drop-in + builds tracer; service
injects tracer and wraps stream (user_id/session_id optional, still works).
- **Tests:** `test_assistant_tracing.py` (NoOp no-ops; LangfuseTracer drives a
  fake langfuse; `build_tracer` gating); extend `test_assistant_service.py`
  (tracer invoked, output set, error path sets error + still emits SSE error
  frame); config-validation test (enabled without keys → error).
- **code-quality-pipeline** (per-file gate).

### M2 — Trace grouping (user + session)
Steps: schema `id` + `session_id()`; router injects current user + passes
user_id/session_id; `.env.example` + docs note.
- **Tests:** `test_assistant_schemas.py` (session_id extraction, missing→None);
  `test_assistant_api.py` (endpoint streams with a stub tracer; asserts
  trace_chat called with the user/session).
- **code-quality-pipeline** (per-file gate).

## Verification (before PR)
- `ruff check` / `ruff format --check`, `mypy`, `pytest` (full suite green).
- Manual/QA: run app with keys set, hit `/assistant/chat`, confirm a single
  grouped trace with nested generations + usage in Langfuse Cloud; run with
  Langfuse disabled and confirm unchanged behaviour + no `langfuse` import.

## Close-out (Phase 3/4)
- Mark milestones DONE/decisions here; update root CLAUDE.md/AGENTS.md env list;
  run claude-md-improver; QA handover on the running app (live `/assistant/chat`).

## Status
- [x] **M1 — Core tracing + config** — DONE. `langfuse>=4.0.0`; 4 config settings +
  startup validation; `assistant/tracing.py` (Tracer/NoOp/Langfuse/build_tracer);
  drop-in selection + tracer injection in `dependencies.py`; service wraps the stream.
- [x] **M2 — Trace grouping** — DONE. `ChatRequest.id` + `session_id()`; router injects
  `get_current_user` and passes `user_id`/`session_id`; `.env.example` + AGENTS.md.
- [x] **Verification** — `ruff` + `mypy` clean repo-wide (123 src files); **293 tests
  pass**. Runtime-verified: disabled path → `NoOpTracer`, `langfuse` never imported,
  plain `openai.AsyncOpenAI`; enabled path → `LangfuseTracer` + `langfuse.openai` drop-in
  wraps `AsyncCompletions.create` (instrumentation confirmed live).
- [ ] **PR opened** — await user confirmation.

### Key decisions (as built)
- **Langfuse v4** (4.14.1 installed) not v3 — API verified: `Langfuse(host=…)`,
  `propagate_attributes(user_id, session_id, tags, trace_name)`, `langfuse.openai` drop-in.
- **`client.py` untouched** — streamed usage relies on the drop-in's built-in capture;
  the `stream_options` fallback was not needed at build time (re-check on live QA).
- **Tracing never fatal** — `LangfuseTracer.trace_chat` guards the span and degrades to a
  no-op on any langfuse error, so observability can never break the chat stream.
- **Global drop-in side effect** — importing `langfuse.openai` wraps the OpenAI SDK
  process-wide; acceptable since config is process-wide.

### Code review (independent pass) — 1 Important finding, fixed
- **Double-yield could break the stream (FIXED).** `LangfuseTracer.trace_chat` originally
  `yield`ed inside a `try/except Exception`; an exception thrown back in *after* the yield
  (e.g. an unguarded `span.update` in `set_output`) would trigger a second yield →
  `RuntimeError("generator didn't stop")`, breaking the SSE response — violating the
  "tracing never fatal" guarantee. Fix: `set_output`/`set_error` now swallow+log SDK
  failures; `trace_chat` enters span/attribute scopes manually, guards **only** setup and
  teardown, and `yield`s outside any catch so body errors propagate unmasked. Locked in by
  `test_langfuse_tracer_swallows_recording_failures` +
  `test_langfuse_tracer_propagates_body_errors_and_still_closes_span`.
- **PHI to Langfuse Cloud (design callout, not a bug).** When enabled, prompts/completions
  (which discuss patients) + the final reply are sent to `LANGFUSE_HOST`. Off by default and
  opt-in, but it contrasts with the local-Ollama-for-summaries stance ("transcripts never
  leave this host"). For a clinical deployment, prefer self-hosted Langfuse and/or output
  masking (`Langfuse(mask=…)`). Surfaced to the user; Langfuse Cloud was the chosen backend.

### Code review (round 2, at PR prep) — 1 Medium + 2 minor, all fixed
- **Orphaned span on partial setup (FIXED, Medium).** `trace_chat` entered the span then
  `propagate_attributes` imperatively; if the second entry raised, the span was never
  exited and leaked into the worker's OTEL context (mis-nesting later requests). Rewritten
  with `ExitStack` so any entered scope is unwound on setup failure. Test:
  `test_langfuse_tracer_rolls_back_span_when_attr_setup_fails`.
- **No shutdown flush (FIXED, Low).** Added `shutdown_tracing()` (flushes the Langfuse
  singleton, no-op + no SDK import if unused), wired into the FastAPI lifespan shutdown.
  Tests: `test_shutdown_tracing_*`.
- **`session_id` ternary (FIXED, simplification).** → `(request.id or "").strip() or None`.
- Reviewers confirmed: no key leakage to client/logs; swallow-and-log blocks are narrow
  and always log; validation correct/complete; no SSRF/injection from `id`/`user_id`.
- Final gate: `ruff format` + `ruff check` clean, `mypy` clean (123 files), **298 tests
  pass**; app imports without loading `langfuse` (disabled-path guarantee re-verified).

### Live QA — DONE (PASS), 2026-07-20
Ran the real stack: backend on :8010 with `LANGFUSE_ENABLED=true` + real OpenAI +
real Langfuse Cloud keys (Postgres already up). `POST /assistant/chat` streamed a
real Hebrew answer cleanly (`start → text-delta… → text-end → finish → [DONE]`),
**no tracing errors in the log**. Verified via the Langfuse API (`auth_check: True`):
- Two `assistant-chat` traces landed, tagged `['assistant']`, grouped by
  `session_id` (`langfuse-smoke-1/2`) + `user_id` (`3fa85f64…` = TEST_USER).
- Each has a nested `GENERATION` (model `gpt-5.4-mini`) with **token usage
  captured on the streamed call** (input 4017 / output 131 / total 4148) and cost
  ($0.0036). **→ `stream_options` fallback NOT needed; item closed.**
- Startup validation passed with enabled+keys.

### Config correction found during QA (fixed)
The repo `.env` uses `LANGFUSE_BASE_URL` (langfuse v4's own var) with no
`LANGFUSE_HOST`. Renamed the setting `langfuse_host` → **`langfuse_base_url`**
(reads `LANGFUSE_BASE_URL`) so operator config is actually honored instead of
silently defaulting to cloud. Updated `.env.example`, `AGENTS.md`, tests.
