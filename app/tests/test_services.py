def test_create_service(isolated_client):
    resp = isolated_client.post(
        "/services", json={"name": "auth-svc", "version": "1.0.0", "status": "green"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "auth-svc"
    assert body["status"] == "green"
    assert "id" in body


def test_create_service_rejects_invalid_status(isolated_client):
    resp = isolated_client.post(
        "/services", json={"name": "auth-svc", "version": "1.0.0", "status": "blue"}
    )
    assert resp.status_code == 422


def test_create_service_rejects_empty_name(isolated_client):
    resp = isolated_client.post(
        "/services", json={"name": "", "version": "1.0.0", "status": "green"}
    )
    assert resp.status_code == 422


def test_list_services_empty(isolated_client):
    resp = isolated_client.get("/services")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_services_returns_created(isolated_client):
    isolated_client.post(
        "/services", json={"name": "billing-svc", "version": "2.1.0", "status": "yellow"}
    )
    resp = isolated_client.get("/services")
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "billing-svc" in names


def test_update_service_status(isolated_client):
    created = isolated_client.post(
        "/services", json={"name": "cache-svc", "version": "0.9.0", "status": "green"}
    ).json()
    resp = isolated_client.put(f"/services/{created['id']}/status", json={"status": "red"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "red"


def test_update_service_status_not_found(isolated_client):
    resp = isolated_client.put("/services/9999/status", json={"status": "red"})
    assert resp.status_code == 404


def test_update_service_status_rejects_invalid_enum(isolated_client):
    created = isolated_client.post(
        "/services", json={"name": "queue-svc", "version": "3.0.0", "status": "green"}
    ).json()
    resp = isolated_client.put(f"/services/{created['id']}/status", json={"status": "purple"})
    assert resp.status_code == 422
