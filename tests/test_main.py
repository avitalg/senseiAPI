from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root_returns_welcome() -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert res.json() == {"message": "Welcome to SenseiAPI"}


def test_health_returns_ok() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_unknown_route_returns_404() -> None:
    res = client.get("/does-not-exist")
    assert res.status_code == 404
