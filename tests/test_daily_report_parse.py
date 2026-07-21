import pytest

from daily_reports.models import DailyReportFailedError
from daily_reports.parse import parse_daily_report_output


def test_parse_daily_report_json() -> None:
    assert parse_daily_report_output('{"text": "תדריך יומי קצר."}') == "תדריך יומי קצר."


def test_parse_daily_report_json_inside_fence() -> None:
    raw = '```json\n{"text": "תדריך יומי."}\n```'

    assert parse_daily_report_output(raw) == "תדריך יומי."


def test_parse_daily_report_json_inside_surrounding_text() -> None:
    raw = 'תוצאה:\n{"text": "תדריך יומי."}\nסוף'

    assert parse_daily_report_output(raw) == "תדריך יומי."


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        "{}",
        '{"text": "   "}',
        '{"text": 123}',
    ],
)
def test_parse_daily_report_rejects_invalid_output(raw: str) -> None:
    with pytest.raises(DailyReportFailedError):
        parse_daily_report_output(raw)
