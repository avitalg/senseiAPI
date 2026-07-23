"""Regenerate ``seeds/patients/*.json`` from the sensei-patients mock corpus.

Development-time tool — the running API never invokes it. Point it at a checkout
of the mock-data repo and it rewrites the committed seed corpus::

    .venv/bin/python -m seeds.generate --source ../sensei-patients/mock_patients

The mock Markdown carries no contact details, so they live in ``CONTACTS`` below:
the four patients that predate this corpus keep the phone and email their old
seed file carried, and the rest get synthetic values.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seeds.mock_parser import (
    MockParseError,
    RecordedSession,
    SummarySection,
    parse_recorded,
    parse_summaries,
)

logger = logging.getLogger(__name__)

# ../sensei-patients sits next to this repository in the same parent directory.
DEFAULT_SOURCE = Path(__file__).resolve().parents[2] / "sensei-patients" / "mock_patients"
OUTPUT_DIR = Path(__file__).with_name("patients")

SEED_USER_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
SESSIONS_PER_PATIENT = 5
TITLE_MAX_LENGTH = 255  # calendar_events.title is String(255)


@dataclass(frozen=True)
class Contact:
    """Contact details for a seeded patient; ``patients.phone`` is not nullable."""

    phone: str
    email: str | None = None


CONTACTS: dict[str, Contact] = {
    "aladdin": Contact("+972-52-4001122", "aladdin@example.com"),
    "bruce_wayne": Contact("+972-54-4002233", "bruce.wayne@example.com"),
    "dumbo": Contact("+972-53-4003344", "dumbo@example.com"),
    "elsa": Contact("+972-52-8877665", "elsa@example.com"),
    "forrest_gump": Contact("+972-50-7654321"),
    "harry_potter": Contact("+972-50-9998887"),
    "marlin": Contact("+972-50-4004455", "marlin@example.com"),
    "moana": Contact("+972-52-4005566", "moana@example.com"),
    "mulan": Contact("+972-54-4006677", "mulan@example.com"),
    "rapunzel": Contact("+972-53-4007788", "rapunzel@example.com"),
    "simba": Contact("+972-50-1234567"),
}


def _session(slug: str, recorded: RecordedSession, summary: SummarySection) -> dict[str, Any]:
    """Join one session's two halves into its seed JSON object."""
    title = f"מפגש {recorded.n}: {recorded.title or summary.title}"
    if len(title) > TITLE_MAX_LENGTH:
        raise MockParseError(
            f"{slug} session {recorded.n}: title is {len(title)} chars (max {TITLE_MAX_LENGTH})"
        )
    if summary.duration_minutes <= 0:
        raise MockParseError(f"{slug} session {recorded.n}: duration must be positive")
    return {
        "n": recorded.n,
        "title": title,
        "start_at": summary.start_at.isoformat(),
        "end_at": summary.end_at.isoformat(),
        "transcript": recorded.transcript,
        "note": recorded.note,
        "summary": summary.text,
    }


def build_patient(slug: str, recorded_text: str, summaries_text: str) -> dict[str, Any]:
    """Turn one patient's two Markdown files into their seed JSON payload."""
    contact = CONTACTS.get(slug)
    if contact is None:
        raise MockParseError(f"{slug}: unknown patient — add an entry to CONTACTS")

    recorded = parse_recorded(recorded_text)
    name, summaries = parse_summaries(summaries_text)
    expected = list(range(1, SESSIONS_PER_PATIENT + 1))
    if sorted(recorded) != expected or sorted(summaries) != expected:
        raise MockParseError(
            f"{slug}: expected sessions {expected}, got "
            f"recorded={sorted(recorded)} summaries={sorted(summaries)}"
        )

    return {
        "user_id": SEED_USER_ID,
        "slug": slug,
        "name": name,
        "phone": contact.phone,
        "email": contact.email,
        "sessions": [_session(slug, recorded[n], summaries[n]) for n in expected],
    }


def generate(source: Path, output_dir: Path) -> list[str]:
    """Write one seed JSON file per mock patient directory; returns the slugs written."""
    directories = sorted(path for path in source.iterdir() if path.is_dir())
    if not directories:
        raise SystemExit(f"No mock patient directories found in {source}")

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for directory in directories:
        slug = directory.name
        payload = build_patient(
            slug,
            (directory / "recorded_sessions.md").read_text(encoding="utf-8"),
            (directory / "session_summaries.md").read_text(encoding="utf-8"),
        )
        destination = output_dir / f"{slug}.json"
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        logger.info("Wrote %s.", destination.name)
        written.append(slug)
    return written


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Regenerate the patient seed corpus.")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"mock_patients directory (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help=f"seed output directory (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    slugs = generate(args.source, args.output)
    logger.info("Done — %d patients written.", len(slugs))


if __name__ == "__main__":
    main()
