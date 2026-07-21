import json
import re

from daily_reports.models import DailyReportFailedError


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text, count=1)
    return text.strip()


def parse_daily_report_output(raw: str) -> str:
    """Extract the required non-empty ``text`` string from model JSON."""
    cleaned = _strip_fences(raw)
    try:
        value: object = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise DailyReportFailedError("the model returned invalid daily report JSON") from None
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise DailyReportFailedError("the model returned invalid daily report JSON") from exc

    if not isinstance(value, dict):
        raise DailyReportFailedError("the model returned invalid daily report JSON")
    text = value.get("text")
    if not isinstance(text, str) or not text.strip():
        raise DailyReportFailedError("the model returned an empty daily report")
    return text.strip()
