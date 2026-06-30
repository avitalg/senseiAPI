from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from analysis.analyzer import Analyzer, MockAnalyzer
from analysis.dependencies import get_analyzer
from analysis.models import AnalysisFailedError, AnalysisResult
from main import app

_MOCK = MockAnalyzer()


class _FailingAnalyzer(Analyzer):
    async def analyze(self, transcript: str) -> AnalysisResult:
        raise AnalysisFailedError("upstream failure")


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_analyzer] = lambda: _MOCK
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def failing_client() -> Iterator[TestClient]:
    app.dependency_overrides[get_analyzer] = lambda: _FailingAnalyzer()
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_analyze_returns_200_with_expected_response(client: TestClient) -> None:
    res = client.post("/analysis", json={"transcript": "Patient discussed the incident."})

    assert res.status_code == 200

    body = res.json()
    assert set(body.keys()) == {"summary", "insights", "risk_flags"}

    assert isinstance(body["summary"], str)
    assert body["summary"]

    assert isinstance(body["insights"], list)
    assert body["insights"]
    assert all(isinstance(insight, str) for insight in body["insights"])

    assert isinstance(body["risk_flags"], list)
    assert body["risk_flags"]
    assert all(isinstance(flag, str) for flag in body["risk_flags"])


def test_analyze_missing_transcript_returns_422(client: TestClient) -> None:
    res = client.post("/analysis", json={})

    assert res.status_code == 422


def test_analyze_returns_502_when_analyzer_fails(failing_client: TestClient) -> None:
    res = failing_client.post("/analysis", json={"transcript": "hello"})

    assert res.status_code == 502
    assert res.json()["detail"] == "Transcript analysis failed."