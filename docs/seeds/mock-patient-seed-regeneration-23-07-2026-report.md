# Patient seed regeneration from mock_patients (23-07-2026)

The seed corpus is now generated from `../sensei-patients/mock_patients` instead
of being written by hand. Eleven patients, five sessions each.

## Regenerating

    .venv/bin/python -m seeds.generate --source ../sensei-patients/mock_patients

Then commit the changed `seeds/patients/*.json`. `seeds/load.py` is unchanged by
a regeneration — it still reads the committed JSON at runtime, so the API never
depends on the mock repo.

New patient in the mock repo? Add a `CONTACTS` entry in `seeds/generate.py` and
add the slug to `EXPECTED_SLUGS` in `tests/test_seed_files.py` — the generator
refuses to write a patient it has no contact details for.

## What changed

- **Roster:** `eeyore`, `gollum`, `hermione`, `shrek` and `woody` are gone — they
  have no mock source. `harry` → `harry_potter`, `forrest` → `forrest_gump`.
  Added `aladdin`, `bruce_wayne`, `dumbo`, `marlin`, `moana`, `mulan`, `rapunzel`.
  `elsa` is a different patient now: the mock file is CFT / self-criticism, the
  old seed was panic + interoceptive exposure. The text for `harry`, `forrest`
  and `simba` was byte-identical to their mock counterparts, so only their
  schedule, name and summary changed.
- **Summaries are real.** `meeting_summaries.text` now holds the structured block
  from `session_summaries.md` verbatim. Previously it held the therapist's
  dictated recording.
- **Transcripts are the recording.** `transcripts.raw_text` is the dictated
  recording followed by the private `🎙️` note. Previously it held only the note.
- **Timestamps carry `+03:00`.** `assistant/context.py` renders stored timestamps
  in Israel time, so the assistant now reports the same time that is printed
  inside the summary text. The old seeds stored `+00:00` and read three hours off.

## Parsing quirks worth knowing

- `simba/recorded_sessions.md` has bare `## מפגש N` headers with no title, so
  simba's titles come from `session_summaries.md`. The header regex separates its
  parts with `[ \t]*` rather than `\s*` — `\s` matches a newline, which would make
  an untitled header swallow the line below it as its title.
- `marlin`'s H1 reads `מרלין (אביו של נמו)` while its metadata line reads `מרלין`.
  Patient names therefore come from the metadata line, not the H1.

## Stale rows

`seeds/load.py` upserts and never deletes. A database seeded with the old corpus
keeps the five removed patients plus orphaned `harry` and `forrest` rows. This is
accepted for demo data — pruning would have to delete by `user_id`, which would
also remove real patients created under the demo therapist. Drop the database to
get a clean roster.
