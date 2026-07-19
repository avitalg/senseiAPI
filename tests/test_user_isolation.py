import uuid
from datetime import UTC, datetime, timedelta

import pytest

from auth.router import get_current_user
from auth.schemas import User
from calendar_events.orm import CalendarEventRecord
from main import app
from patients.orm import PatientRecord
from summaries.orm import SummaryRecord
from tests.conftest import ClientFactory
from tests.database_helpers import get_database_url
from transcripts.orm import TranscriptRecord

USER_ONE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_TWO_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _user(user_id: uuid.UUID) -> User:
    return User(
        user_id=user_id,
        email=f"{user_id}@example.com",
        full_name="Test User",
    )


def test_tenant_keys_begin_with_the_user_id() -> None:
    assert [column.name for column in PatientRecord.__table__.primary_key] == ["user_id", "id"]
    assert [column.name for column in CalendarEventRecord.__table__.primary_key] == [
        "user_id",
        "id",
    ]
    assert [column.name for column in TranscriptRecord.__table__.primary_key] == ["user_id", "id"]
    assert [column.name for column in SummaryRecord.__table__.primary_key] == ["user_id", "id"]


@pytest.mark.integration
def test_users_cannot_access_each_others_patients_calendar_or_meeting_uploads(
    make_client: ClientFactory,
) -> None:
    current_user = _user(USER_ONE_ID)
    app.dependency_overrides[get_current_user] = lambda: current_user

    try:
        with get_database_url() as database_url:
            client, _ = make_client(database_url=database_url)
            with client:
                patient_response = client.post(
                    "/patients",
                    json={"name": "Owned Patient", "phone": "050-0000000"},
                )
                assert patient_response.status_code == 201
                patient_id = patient_response.json()["id"]

                start_at = datetime(2026, 7, 11, 9, 0, tzinfo=UTC)
                event_response = client.post(
                    "/calendar",
                    json={
                        "title": "Owned Meeting",
                        "start_at": start_at.isoformat(),
                        "end_at": (start_at + timedelta(minutes=50)).isoformat(),
                        "patient_id": patient_id,
                    },
                )
                assert event_response.status_code == 201
                event_id = event_response.json()["id"]

                current_user = _user(USER_TWO_ID)

                assert client.get("/patients").json() == []
                assert client.get("/calendar?from=2026-07-11&to=2026-07-11").json() == []
                assert client.get(f"/calendar/{event_id}").status_code == 404
                assert (
                    client.patch(
                        f"/patients/{patient_id}", json={"phone": "050-1111111"}
                    ).status_code
                    == 404
                )
                assert (
                    client.patch(f"/calendar/{event_id}", json={"title": "Changed"}).status_code
                    == 404
                )
                assert client.delete(f"/patients/{patient_id}").status_code == 404
                assert client.delete(f"/calendar/{event_id}").status_code == 404

                cross_user_event = client.post(
                    "/calendar",
                    json={
                        "title": "Cross-user patient",
                        "start_at": start_at.isoformat(),
                        "end_at": (start_at + timedelta(minutes=50)).isoformat(),
                        "patient_id": patient_id,
                    },
                )
                assert cross_user_event.status_code == 404

                upload_response = client.post(
                    "/audio/upload",
                    files={"file": ("meeting.mp3", b"audio", "audio/mpeg")},
                    data={"meeting_id": event_id},
                )
                assert upload_response.status_code == 404

                current_user = _user(USER_ONE_ID)
                assert len(client.get("/patients").json()) == 1
                assert len(client.get("/calendar?from=2026-07-11&to=2026-07-11").json()) == 1
                assert client.get(f"/calendar/{event_id}").status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)
