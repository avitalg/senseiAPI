# Patient seed expansion — 6 new patients (20-07-2026)

Expanded the demo seed corpus from **3 → 9 patients** so `senseiapi` has richer,
more varied data for demos and testing. Each patient is a well-known fictional
character reframed as a therapy client (matching the existing forrest/simba/harry
pattern), with a full end-to-end data chain: **patient → 5 weekly calendar events
→ 5 transcripts (dictated clinical notes) → 5 session summaries**.

## What was added

Six new files under `seeds/patients/` (auto-discovered by `seeds/load.py`'s
`*.json` glob — no loader change needed):

| File | Patient | Persona | Clinical presentation | Modality | Calendar slot |
|---|---|---|---|---|---|
| `eeyore.json` | איה | Eeyore | Depression / dysthymia, anhedonia | CBT + Behavioral Activation | Mon 08:00 |
| `elsa.json` | אלזה | Elsa | Panic disorder + emotional suppression | DBT + interoceptive exposure | Wed 09:00 |
| `hermione.json` | הרמיוני | Hermione | Perfectionism / GAD, burnout | CBT + self-compassion | Thu 13:00 |
| `shrek.json` | שרק | Shrek | Social anxiety / avoidant, shame | CFT + ACT | Mon 15:00 |
| `gollum.json` | גולום | Gollum | Addiction / ambivalence | Motivational Interviewing + relapse prevention | Wed 07:00 |
| `woody.json` | וודי | Woody | Attachment / abandonment, self-worth | Schema + attachment work | Fri 08:00 |

The clinical presentations were deliberately chosen to **not overlap** with the
existing trio (Forrest = combat PTSD/grief, Simba = guilt/EMDR, Harry =
childhood trauma/EMDR), broadening the demo beyond trauma/EMDR.

Each patient runs the same 5-week span as the existing seeds (mid-June →
mid-July 2026), on a **distinct weekday + time slot** so the therapist's calendar
looks like a real practice with no double-bookings.

## How it was generated

A background **workflow** (`generate-patient-seeds`) with 12 agents:

1. **Research & Draft** (6 parallel agents) — each researched the character's
   canon, mapped it to the assigned presentation, and drafted a coherent
   5-session Hebrew therapeutic arc (rapport → assessment → core work →
   processing → integration) in the established dictated-note voice.
2. **Verify** (6 parallel adversarial agents) — a senior-supervisor + native-Hebrew
   editor pass that fixed issues **in place**. It caught real defects: Latin
   transliterations (`פסיכו-אדיוקציה`→`פסיכו-חינוך`, `טריגרים`, `היפרוונטילציה`,
   `CFT`/`ACT` acronyms, `פרוקסי`, `אינדיקטור`) and spelling errors.

Identity, phone numbers, calendar slots, and session timestamps were assigned
**deterministically by an assembler script** (not the LLM) to guarantee no
duplicate slugs/phones and no calendar collisions — the agents produced only the
clinical text (title/summary/transcript).

## Verification (e2e)

- **Static:** JSON schema completeness, session ordering, unique slugs/phones,
  no emoji, no Latin letters in clinical text, no cross-patient double-bookings —
  all 9 patients pass.
- **Live DB load:** ran `.venv/bin/python -m seeds.load` against local Postgres
  (idempotent, deterministic uuid5 ids). Result: **9 patients, 45 calendar_events,
  45 transcripts, 45 meeting_summaries** — every patient verified to have a
  complete 5/5/5 chain.

## Re-running

```bash
.venv/bin/python -m seeds.load   # idempotent — upserts, safe to re-run
```
