# Mock-patient seed regeneration — design

**Date:** 2026-07-23
**Status:** approved

## Goal

Replace the hand-written `seeds/patients/*.json` corpus with data generated from
the canonical mock-data repo at `../sensei-patients/mock_patients`, so the demo
database carries all 11 patients and — for the first time — real structured
session summaries.

## Why

`seeds/patients/*.json` was derived by hand from an earlier revision of the mock
repo. Comparing the two revealed:

| slug | mock counterpart | verdict |
|---|---|---|
| `harry` | `harry_potter` | byte-identical text, all 5 sessions |
| `forrest` | `forrest_gump` | byte-identical text, all 5 sessions |
| `simba` | `simba` | byte-identical text, all 5 sessions |
| `elsa` | `elsa` | **different patient** — mock is CFT / self-criticism / injuring Anna; the seed is panic + interoceptive exposure |
| `eeyore`, `gollum`, `hermione`, `shrek`, `woody` | none | no mock source |
| — | `aladdin`, `bruce_wayne`, `dumbo`, `marlin`, `moana`, `mulan`, `rapunzel` | 7 new |

The mock repo has since gained a second artifact per patient,
`session_summaries.md` — structured system-output summaries that the seed corpus
has no equivalent of. It also carries real schedule metadata (date, time,
duration) that the hand-written seeds diverge from.

The existing seeds also map the two text artifacts **backwards**: the therapist's
dictated recording is stored as the session *summary*, and the private clinical
note is stored as the *transcript*. The dictated recording is the transcript; the
structured block is the summary.

## Source data

Each of the 11 `mock_patients/<slug>/` directories holds two Markdown files.

`recorded_sessions.md`:

```
# <name> — תיק מטופל (Mock Data)

**גישה טיפולית מרכזית:** ...
**רקע קליני:** ...

---

## מפגש 1: <title>

"<dictated therapist recording>"

🎙️ הקלטת המטפל (Note): "<private clinical note>"

---
```

`session_summaries.md`:

```
# <name> — סיכומי מפגשים (פלט מערכת)

---

## פגישה 1
<title>

<name> · DD/MM/YY · HH:MM · N דק׳

**תובנות מרכזיות**
...

**סיכום הפגישה**
...

**נושאים מרכזיים**
- ...

**דגלי סיכון**
*(אינדיקטור בלבד. אינו מהווה אבחנה רפואית)*
**<level>** — ...

---
```

Verified uniform across all 11 patients: 5 sessions each, weekly cadence, one
`## מפגש N` per session, one `## פגישה N` per session, one metadata line per
summary block.

Two format irregularities the parser must handle:

- **`simba/recorded_sessions.md` has no per-session titles** — its headers are a
  bare `## מפגש 1`. Titles for simba come from `session_summaries.md`.
- **`marlin`'s H1 reads `מרלין (אביו של נמו)`** while its metadata line reads
  `מרלין`. Patient names are therefore taken from the metadata line, not the H1.

## Data flow

```
sensei-patients/mock_patients/<slug>/*.md
            ↓  seeds/generate.py    (dev-time, run by hand)
seeds/patients/<slug>.json          (committed, 11 files)
            ↓  seeds/load.py        (runtime)
          database
```

The generator runs at development time only. The API never reads the external
repo — `seeds/load.py` keeps reading committed JSON, unchanged in that respect.

## Field mapping

| DB column | source |
|---|---|
| `patients.name` | metadata-line name |
| `patients.phone` / `.email` | generator's per-slug contact table (see below) |
| `calendar_events.title` | `מפגש N: <title>`; title from the `## מפגש N:` header, falling back to the `## פגישה N` title line when the header carries none |
| `calendar_events.start_at` | metadata line `DD/MM/YY · HH:MM`, tz `Asia/Jerusalem` |
| `calendar_events.end_at` | `start_at + N דק׳` (dumbo = 40 min, the rest 50) |
| `calendar_events.description` | `None` (unchanged) |
| `transcripts.raw_text` | dictated recording, then a blank line, then `🎙️ הקלטת המטפל (Note): <note>` |
| `transcripts.language` | `"he"` (unchanged) |
| `meeting_summaries.text` | the `## פגישה N` block verbatim — title line, metadata line and all four content blocks |
| `meeting_summaries.status` | `"ready"` (unchanged) |

### Seed JSON shape

The per-session object gains one key, `note`. Everything else is unchanged, so
`seeds/load.py` stays backward-compatible with any file that omits it.

```json
{
  "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "slug": "moana",
  "name": "מואנה",
  "phone": "+972-52-4005566",
  "email": "moana@example.com",
  "sessions": [
    {
      "n": 1,
      "title": "מפגש 1: היכרות ומיפוי \"הסיפור השולט\"",
      "start_at": "2026-06-23T17:00:00+03:00",
      "end_at": "2026-06-23T17:50:00+03:00",
      "transcript": "<dictated recording>",
      "note": "<private clinical note>",
      "summary": "<verbatim summary block>"
    }
  ]
}
```

`seeds/load.py` composes `transcripts.raw_text` from `transcript` + `note` at
load time rather than the generator pre-joining them, so the JSON stays a
lossless, individually addressable record of the source.

## Decisions

**Slugs follow the mock directory names.** `harry` → `harry_potter`, `forrest` →
`forrest_gump`. Slug always equals the mock directory, so regenerating needs no
lookup table.

**The five seeds with no mock source are deleted** (`eeyore`, `gollum`,
`hermione`, `shrek`, `woody`). `mock_patients` becomes the single source of
truth; keeping them would leave five patients with the old backwards mapping and
no structured summary.

**Timestamps carry an `Asia/Jerusalem` offset.** `assistant/context.py:39`
(`_readable`) converts stored timestamps to Israel time before showing them to
the assistant. The existing seeds store `+00:00`, so a `09:00` seed surfaces as
`12:00`. Storing `2026-06-21T14:30:00+03:00` makes what the assistant says match
the time printed inside the summary text. Every mock date falls in June–July
2026, entirely within IDT.

**Summaries are stored verbatim.** The mock format
(`**תובנות מרכזיות**` / `**סיכום הפגישה**` / `**נושאים מרכזיים**` /
`**דגלי סיכון**`) differs from what `summaries/format.py:58`
(`summary_json_to_markdown`) emits today (`## נושאים מרכזיים` /
`## התערבויות המטפל/ת` / `## סימני סיכון` / `## המשך ומעקב`). Verbatim is
lossless and treats `mock_patients` as the design-of-record. Nothing downstream
breaks: `normalize_summary_output` passes non-JSON markdown through untouched,
and `reports/synthesizer.py:49` feeds summary text to the model as free prose.

**Contact data lives in the generator.** The mock files carry no phone or email.
`elsa`, `harry_potter`, `forrest_gump` and `simba` keep the values already in
their seed JSON; the seven new patients get synthetic ones. `patients.phone` is
non-nullable, so every patient needs a number.

| slug | phone | email |
|---|---|---|
| `aladdin` | `+972-52-4001122` | `aladdin@example.com` |
| `bruce_wayne` | `+972-54-4002233` | `bruce.wayne@example.com` |
| `dumbo` | `+972-53-4003344` | `dumbo@example.com` |
| `elsa` | `+972-52-8877665` | `elsa@example.com` |
| `forrest_gump` | `+972-50-7654321` | *(none)* |
| `harry_potter` | `+972-50-9998887` | *(none)* |
| `marlin` | `+972-50-4004455` | `marlin@example.com` |
| `moana` | `+972-52-4005566` | `moana@example.com` |
| `mulan` | `+972-54-4006677` | `mulan@example.com` |
| `rapunzel` | `+972-53-4007788` | `rapunzel@example.com` |
| `simba` | `+972-50-1234567` | *(none)* |

**Stale rows are accepted.** `session.merge` never deletes, so a database seeded
with the old corpus keeps five dead patients plus orphaned `harry` and `forrest`
rows after the slug rename. No pruning code and no documented wipe procedure —
a prune would have to delete by `user_id`, which would also delete real patients
created under the demo therapist.

## Schedule

The mock schedule produces no double-bookings — 11 patients across five weekdays:

| day | patients |
|---|---|
| Sunday | simba 10:00, elsa 14:30 |
| Monday | forrest_gump 11:00, marlin 16:00 |
| Tuesday | harry_potter 12:00, moana 17:00 |
| Wednesday | bruce_wayne 10:30, mulan 15:00 |
| Thursday | rapunzel 13:00, dumbo 16:00, aladdin 18:00 |

All five sessions run weekly from the first date, 21/06/2026 through 23/07/2026.

## Components

**`seeds/mock_parser.py`** — pure functions over Markdown text. No filesystem, no
network. Parses one `recorded_sessions.md` into `{n: RecordedSession}` and one
`session_summaries.md` into `(patient_name, {n: SummarySection})`. Raises
`MockParseError` on anything malformed, so a source change fails loudly instead
of silently producing a partial corpus.

**`seeds/generate.py`** — CLI. Walks the mock directory, calls the parser, joins
the two halves by session number, attaches contact data, writes
`seeds/patients/<slug>.json`. Validates before writing: 5 sessions numbered 1–5,
`end_at > start_at`, title ≤ 255 chars (the `calendar_events.title` column
limit), non-empty transcript/note/summary.

**`seeds/load.py`** — one change: `raw_text` is composed from `transcript` and
the new optional `note` key.

## Testing

**`tests/test_mock_parser.py`** — parser units against inline fixture Markdown:
titled and untitled `## מפגש N` headers, the note not being swallowed into the
transcript, metadata-line parsing (date, time, duration), name taken from the
metadata line, and `MockParseError` on missing sections, a missing metadata line
and mismatched session numbering.

**`tests/test_seed_generate.py`** — generator units against a temporary mock
directory written by the test: the emitted JSON shape, `end_at = start_at + dur`,
the title fallback for untitled headers, contact-table application, and the
validation failures.

**`tests/test_seed_files.py`** — validates the 11 committed JSON files: slug set
matches the expected roster, sessions numbered 1–5, `end_at > start_at`, titles
within 255 chars, transcript/note/summary non-empty, timestamps parse and carry a
`+03:00` offset, and no two patients share a start time.

**`tests/test_seed_load.py`** — `raw_text` composition: transcript plus note when
`note` is present, transcript alone when it is absent or empty.

No test touches the network, the external mock repo, or a live database.
