import pytest


@pytest.fixture
def admin_client():
    from so.admin import app
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client


def test_session_cookie_is_lax():
    from so.admin import app
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


@pytest.mark.parametrize("headers, rejected", [
    ({"Origin": "http://evil.example"}, True),
    ({"Referer": "http://evil.example/page"}, True),
    ({"Origin": "http://localhost:8080"}, False),  # nginx forwards Host without the port
    ({}, False),  # scripts send neither
])
def test_cross_origin_posts_rejected(admin_client, headers, rejected):
    response = admin_client.post("/stop", headers=headers, base_url="http://localhost")
    if rejected:
        assert response.status_code == 403
    else:
        # reaches the route, which sends a logged-out client to the login page
        assert response.status_code == 302


@pytest.fixture
def logged_in(admin_client):
    with admin_client.session_transaction() as session:
        session["admin"] = True
    return admin_client


@pytest.mark.parametrize("path", ["/api/change_password", "/api/command", "/api/override/set",
                                  "/api/override/unset", "/api/scenario/load", "/api/set-data-proxy"])
@pytest.mark.parametrize("kwargs", [{}, {"data": "not json", "content_type": "application/json"}])
def test_json_routes_reject_missing_body(logged_in, path, kwargs):
    assert logged_in.post(path, **kwargs).status_code == 400


def _fake_response(status_code, body):
    from types import SimpleNamespace
    return SimpleNamespace(status_code=status_code, json=lambda: body, text=str(body))


def test_backend_error_detail_is_kept(logged_in, monkeypatch):
    import so.admin
    detail = "invalid value for status_dl: expected one of: NO_RF, FRAME_LOCK"
    monkeypatch.setattr(so.admin.requests, "post", lambda *a, **k: _fake_response(400, {"detail": detail}))
    response = logged_in.post("/api/override/set", json={"attr": "status_dl", "value": "x"})
    assert response.status_code == 400
    assert response.get_json()["error"] == detail


def test_safe_mode_reports_failure(logged_in, monkeypatch):
    import so.admin
    monkeypatch.setattr(so.admin.requests, "post", lambda *a, **k: _fake_response(400, {"detail": "sim stopped"}))
    response = logged_in.post("/api/safe-mode")
    assert response.status_code == 502
    assert response.get_json()["error"] == "sim stopped"
