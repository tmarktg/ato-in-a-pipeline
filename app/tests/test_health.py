def test_healthz_ok(isolated_client):
    resp = isolated_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readyz_ok(isolated_client):
    resp = isolated_client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


def test_readyz_returns_503_when_db_check_fails(isolated_client):
    from app.main import app
    from app.models import get_db

    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("db down")

        def close(self):
            pass

    def broken_db():
        yield BrokenSession()

    original_override = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = broken_db
    try:
        resp = isolated_client.get("/readyz")
    finally:
        app.dependency_overrides[get_db] = original_override
    assert resp.status_code == 503


def test_metrics_exposed(isolated_client):
    resp = isolated_client.get("/metrics")
    assert resp.status_code == 200
    assert b"python_info" in resp.content or b"# HELP" in resp.content
