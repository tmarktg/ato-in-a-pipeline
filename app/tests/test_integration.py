def test_full_lifecycle_against_real_temp_db(client):
    """Integration test: exercises FastAPI + SQLAlchemy against a real temp-file SQLite DB."""
    ready = client.get("/readyz")
    assert ready.status_code == 200

    created = client.post(
        "/services",
        json={"name": "readiness-board", "version": "0.1.0", "status": "green"},
    )
    assert created.status_code == 201
    service_id = created.json()["id"]

    listed = client.get("/services")
    assert any(s["id"] == service_id for s in listed.json())

    updated = client.put(f"/services/{service_id}/status", json={"status": "yellow"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "yellow"

    refetched = client.get("/services")
    match = next(s for s in refetched.json() if s["id"] == service_id)
    assert match["status"] == "yellow"
