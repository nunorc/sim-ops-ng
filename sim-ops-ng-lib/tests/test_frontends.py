import json

import pytest

from conftest import ws_protocols


STATE = {
    "type": "state",
    "ts": 1693111200.0,
    "running": True,
    "paused": False,
    "data_proxy": "SLE",
    "sle_connected": False,
    "breakpoint": {"name": "pass_1", "begin": "b", "end": "e",
                   "ground_station": {"name": "ESOC-1", "latitude": 49.8, "longitude": 8.6, "altitude": 150},
                   "sc_initial_state": {"dhs_memory": 10}},
    "spacecraft": None,  # SLE without FRAME_LOCK: nothing for operators
    "spacecraft_admin": {"aocs_position": [1.0, 2.0, 500.0], "aocs_rotation": [0.0, 0.0, 0.0],
                         "aocs_mode": "NADIR", "is_sunlit": True, "dhs_memory": 42.0, "ttc_mode": "S_Sup_LBR"},
    "ground_station": {"elevation": 12.0, "azimuth": 90.0, "distance": 1500.0, "ul_state": "NO_RF",
                       "status_dl": "PLL_LOCK", "next_pass_start": 1.0, "next_pass_end": 2.0,
                       "next_5_start": 1.5, "next_5_end": 1.8, "power_ul": 50.0, "spectrum_dl": [[1, 2]]},
    "tc_stack": [{"command": "TC_DHS_001"}],
    "tc_history": [],
}


@pytest.fixture
def api(offline_api):
    return offline_api


# ---- WebSocket feeds ----

def test_viewer_feed_needs_no_password(api):
    api_obj, client = api
    api_obj._current_state = dict(STATE)
    with client.websocket_connect("/api/ws/viewer") as ws:
        state = ws.receive_json()
    assert state["type"] == "state"


def test_viewer_feed_is_a_read_only_subset(api):
    api_obj, client = api
    api_obj._current_state = dict(STATE)
    with client.websocket_connect("/api/ws/viewer") as ws:
        state = ws.receive_json()

    # ground truth position/attitude, even without FRAME_LOCK
    assert state["spacecraft"] == {"aocs_position": [1.0, 2.0, 500.0], "aocs_rotation": [0.0, 0.0, 0.0],
                                   "aocs_mode": "NADIR"}
    assert state["breakpoint"] == {"name": "pass_1", "ground_station": STATE["breakpoint"]["ground_station"]}
    assert set(state["ground_station"]) == {"elevation", "distance", "ul_state", "status_dl",
                                            "next_pass_start", "next_pass_end", "next_5_start", "next_5_end"}
    for key in ("spacecraft_admin", "tc_stack", "tc_history", "data_proxy"):
        assert key not in state


def test_viewer_feed_accepts_browser_subprotocol(api):
    api_obj, client = api
    api_obj._current_state = dict(STATE)
    with client.websocket_connect("/api/ws/viewer", subprotocols=["sim-ops"]) as ws:
        assert ws.accepted_subprotocol == "sim-ops"


@pytest.mark.parametrize("path, password, spacecraft", [
    ("/api/ws", "user-pw", None),
    ("/api/ws/admin", "admin-pw", STATE["spacecraft_admin"]),
])
def test_feeds_send_latest_state_on_connect(api, path, password, spacecraft):
    api_obj, client = api
    api_obj._current_state = dict(STATE)
    with client.websocket_connect(path, subprotocols=ws_protocols(password)) as ws:
        state = ws.receive_json()
    assert state["spacecraft"] == spacecraft
    assert "spacecraft_admin" not in state
    assert state["tc_stack"] == STATE["tc_stack"]


# ---- Admin app ----

def test_admin_session_holds_no_password():
    from so import admin

    assert admin.app.secret_key  # never empty, even without FLASK_SECRET_KEY
    client = admin.app.test_client()
    client.post("/login", data={"password": admin.ADMIN_PASSWORD})
    with client.session_transaction() as sess:
        assert sess.get("admin") is True
        assert admin.ADMIN_PASSWORD not in json.dumps(dict(sess))


def test_admin_panel_embeds_user_password_as_js_literal(monkeypatch):
    from so import admin

    password = "it's</script><b>"

    def fake_backend_get(path):
        if path == "/api/admin/user-password":
            return {"password": password}, 200
        return {}, 503

    monkeypatch.setattr(admin, "_backend_get", fake_backend_get)
    client = admin.app.test_client()
    client.post("/login", data={"password": admin.ADMIN_PASSWORD})
    html = client.get("/").get_data(as_text=True)

    # a JSON string literal, with nothing that ends the string or the script
    assert "new SimOpsClient(wsUrl, adminPassword, \"it\\u0027s\\u003c/script\\u003e\\u003cb\\u003e\");" in html
    assert "it's</script>" not in html


def test_mcs_state_types_are_current():
    """The MCS's generated state types match the dataclasses: rerun bin/gen-ts-types.py after changing them."""
    from pathlib import Path
    from so.ts_types import render_ts_types
    generated = Path(__file__).resolve().parents[2] / "sim-ops-ng-mcs" / "src" / "types" / "state.ts"
    assert generated.read_text(encoding="utf-8") == render_ts_types()
