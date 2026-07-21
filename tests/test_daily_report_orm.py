from typing import cast

from sqlalchemy import Table, UniqueConstraint

from daily_reports.orm import DailyMeetingReportRecord


def test_daily_report_is_unique_by_user_and_date_without_time_zone() -> None:
    table = cast(Table, DailyMeetingReportRecord.__table__)
    constraints = [
        constraint for constraint in table.constraints if isinstance(constraint, UniqueConstraint)
    ]
    columns = [{column.name for column in constraint.columns} for constraint in constraints]

    assert {"user_id", "report_date"} in columns
    assert all("time_zone" not in names for names in columns)
