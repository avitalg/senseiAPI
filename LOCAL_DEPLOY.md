# Local deploy — full stack (backend + frontend)

Run the whole Sensei demo locally: this **senseiAPI** backend (FastAPI + Postgres) and
the **Sensei** frontend (Vite/React, repo [`avitalg/SENSEI`](https://github.com/avitalg/SENSEI)).
The two repos are independent — clone them side by side.

## Prerequisites
- **Docker** (for Postgres) · **Python 3.11** (backend venv) · **Node ≥ 18** (frontend)
- An **OpenAI API key** — only needed for live "שאל את סנסיי" answers; everything else runs without it.

## 1 · Backend — API + database (this repo)

```bash
# Postgres — auto-loads the canonical demo seed (patients + sessions + ready summaries)
# from .docker/initdb/ the first time its data dir is empty.
docker compose up -d

# App config — created once from the template; set OPENAI_API_KEY for live assistant answers.
cp .env.example .env

# Python venv (first run only), then the API on http://localhost:8000
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --port 8000 --reload
```

**From scratch** (wipe + reseed the demo data): the DB is a bind mount, and the seed only
re-runs when the data dir is empty —

```bash
docker compose down
rm -rf .docker/postgres_data
docker compose up -d
```

**Config** (`.env`):
- `OPENAI_API_KEY` — set it for live assistant answers.
- `DATABASE_URL` — defaults to the compose Postgres; no change needed.
- `ENABLE_SECURITY` — leave unset in dev: requests resolve to a fixed `TEST_USER` that
  owns the seeded data (no login needed).
- `ASSISTANT_ALLOW_ALL_GETS=true` — lets the assistant reach session summaries for the demo.
- `CORS_ORIGINS` — already allows `http://localhost:3110` (the frontend).

**Verify:**
```bash
curl -s localhost:8000/health
curl -s localhost:8000/assistant/context/patients    # canonical roster (הארי / סימבה / פורסט)
```

## 2 · Frontend — the app

In the sibling `SENSEI` checkout (see its `LOCAL_DEPLOY.md`):
```bash
npm install
echo 'VITE_API_BASE_URL=http://localhost:8000' > .env.local   # API-connected mode
npm run dev                                                    # http://localhost:3110
```
Omit the `.env.local` line for demo mode (no backend). Login is mock auth:
**`rotem@clinic.co.il` / `demo1234`**.

## 3 · Verify the assistant end-to-end
Open **"שאל את סנסיי"** and click **"סכמו את הפגישה האחרונה עם סימבה"** — the panel runs the
tool chain (patients → meetings → summary) and returns the seeded summary with a numeric date.

## Ports
| Service | URL |
|---|---|
| API | http://localhost:8000 (`/docs`) |
| Postgres | localhost:5432 (`sensei` / `sensei`) |
| Frontend | http://localhost:3110 |
