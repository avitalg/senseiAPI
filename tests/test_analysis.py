from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from analysis.analyzer import MockAnalyzer
from analysis.dependencies import get_analyzer
from main import app

_MOCK = MockAnalyzer()


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_analyzer] = lambda: _MOCK
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_analyze_returns_200_with_all_fields(client: TestClient) -> None:
    res = client.post("/analysis", json={"transcript": "Patient discussed the incident."})
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body["summary"], str) and body["summary"]
    assert isinstance(body["insights"], list) and body["insights"]
    assert isinstance(body["risk_flags"], list) and body["risk_flags"]


def test_analyze_is_deterministic(client: TestClient) -> None:
    payload = {"transcript": "Any transcript text."}
    first = client.post("/analysis", json=payload).json()
    second = client.post("/analysis", json=payload).json()
    assert first == second


def test_analyze_same_result_regardless_of_transcript(client: TestClient) -> None:
    res_a = client.post("/analysis", json={"transcript": "Session A content."}).json()
    res_b = client.post("/analysis", json={"transcript": "Completely different session."}).json()
    assert res_a == res_b


def test_analyze_missing_transcript_returns_422(client: TestClient) -> None:
    res = client.post("/analysis", json={})
    assert res.status_code == 422


def test_analyze_response_shape_matches_schema(client: TestClient) -> None:
    res = client.post("/analysis", json={"transcript": "Some text."})
    body = res.json()
    assert set(body.keys()) == {"summary", "insights", "risk_flags"}
    assert all(isinstance(i, str) for i in body["insights"])
    assert all(isinstance(f, str) for f in body["risk_flags"])
