import pytest

from conftest import free_port, wait_for, ws_protocols


# ---- Authentication ----

@pytest.fixture
def api_client(offline_api):
    return offline_api[1]


@pytest.mark.parametrize("method, path", [
    ("post", "/api/control"),
    ("get", "/api/obj-store/tm"),
    ("get", "/api/obj-store/fd"),
    ("get", "/api/obj-store/sp/sim-demo-tm/1"),
])
def test_operator_endpoints_require_password(api_client, method, path):
    body = {"json": {"system": "ground_station", "control": "sweep", "value": True}} if method == "post" else {}

    assert getattr(api_client, method)(path, **body).status_code == 401
    assert getattr(api_client, method)(path, headers={"X-User-Password": "wrong"}, **body).status_code == 401
    for headers in ({"X-User-Password": "user-pw"}, {"X-Admin-Password": "admin-pw"}):
        assert getattr(api_client, method)(path, headers=headers, **body).status_code != 401


class _FakeResponse:
    def __init__(self, body: bytes):
        self.body = body
        self.closed = self.released = False

    def read(self):
        return self.body

    def json(self):
        raise ValueError("not JSON")

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


@pytest.mark.parametrize("is_json", [False, True])
def test_object_store_releases_responses(no_minio, is_json):
    """Each get_object response holds a pooled connection until released, even if decoding fails."""
    from so.core import ObjectStore
    store = ObjectStore()
    responses = []

    def get_object(bucket, name):
        responses.append(_FakeResponse(b"packet"))
        return responses[-1]
    store.client.get_object = get_object

    if is_json:
        with pytest.raises(ValueError):
            store.get("sim-demo-tm", "1", is_json=True)
    else:
        assert store.get("sim-demo-tm", "1") == b"packet"
    assert responses and all(r.closed and r.released for r in responses)


def test_passwords_not_accepted_in_query(api_client):
    assert api_client.get("/api/auth", params={"x_user_password": "user-pw"}).status_code == 401
    assert api_client.get("/api/auth", headers={"X-User-Password": "user-pw"}).status_code == 200


@pytest.mark.parametrize("path, password", [("/api/ws", "user-pw"), ("/api/ws/admin", "admin-pw")])
def test_websocket_auth_via_subprotocol(api_client, path, password):
    from starlette.websockets import WebSocketDisconnect

    with api_client.websocket_connect(path, subprotocols=ws_protocols(password)) as ws:
        assert ws.accepted_subprotocol == "sim-ops"

    for protocols in (None, ws_protocols("wrong"), ["sim-ops", "sim-ops.password.!!"]):
        with pytest.raises(WebSocketDisconnect):
            with api_client.websocket_connect(path, subprotocols=protocols):
                pass
    with pytest.raises(WebSocketDisconnect):
        with api_client.websocket_connect(f"{path}?x_user_password={password}&x_admin_password={password}"):
            pass


# ---- Status codes ----

@pytest.fixture
def fake_sim_api(monkeypatch):
    """API wired to a stub sim socket server whose handler results each test sets."""
    from fastapi.testclient import TestClient
    from so.api import SimOpsAPI
    from so.communication import SocketServer
    from so.core import ObjectStore
    monkeypatch.setenv("SIM_OPS_NG_ADMIN_PASSWORD", "admin-pw")
    monkeypatch.setattr(ObjectStore.__init__, "__defaults__", ("127.0.0.1:1", "user", "password"))

    results = {}
    port = free_port()
    server = SocketServer(port=port)
    monkeypatch.setenv("SIM_OPS_NG_USER_PASSWORD", "user-pw")
    for command in ("start", "next_breakpoint", "previous_breakpoint", "admin_set_state",
                    "control", "tc_send", "tc_stack_push", "tc_stack_delete", "tc_stack_execute",
                    "get_scenario", "set_data_proxy", "unset_override"):
        server.register_handler(command, lambda params, c=command: results[c])
    server.start()
    assert wait_for(lambda: server._server_socket is not None)

    api = SimOpsAPI(simops_port=port)
    with TestClient(api.api) as client:
        client.headers["X-Admin-Password"] = "admin-pw"
        yield client, results
    server.stop()


def test_api_reports_sim_failures(fake_sim_api):
    client, results = fake_sim_api

    results["next_breakpoint"] = {"success": False, "status": "no_next_breakpoint", "breakpoint": {"name": "pass_4"}}
    assert client.post("/api/next-breakpoint").status_code == 400
    results["previous_breakpoint"] = {"success": False, "status": "no_previous_breakpoint"}
    assert client.post("/api/previous-breakpoint").status_code == 400
    results["admin_set_state"] = {"success": False, "error": "Unknown attribute: foo"}
    response = client.post("/api/admin/set-state", json={"attr": "foo", "value": "1"})
    assert response.status_code == 400 and "foo" in response.json()["detail"]
    results["start"] = {"success": False, "error": "Unknown breakpoint: 'x'"}
    assert client.post("/api/start").status_code == 400
    results["start"] = {"success": False, "status": "already_running", "error": "Simulation is already running"}
    assert client.post("/api/start").status_code == 409


def test_api_reports_data_proxy_and_unset_override_failures(fake_sim_api):
    client, results = fake_sim_api
    results["set_data_proxy"] = {"success": False, "error": "Unknown mode: FOO. Valid: EGSE, SLE"}
    response = client.post("/api/data-proxy", json={"mode": "foo"})
    assert response.status_code == 400 and "FOO" in response.json()["detail"]
    results["set_data_proxy"] = {"success": True, "mode": "SLE"}
    response = client.post("/api/data-proxy", json={"mode": "sle"})
    assert response.status_code == 200 and response.json()["mode"] == "SLE"

    # while the sim runs, the handler's failure comes back from the sim thread as data.success False
    results["unset_override"] = {"success": False, "error": "Attribute name required"}
    response = client.post("/api/override/unset", json={"attr": "", "value": ""})
    assert response.status_code == 400 and "Attribute" in response.json()["detail"]
    results["unset_override"] = {"attr": "dhs_memory"}
    response = client.post("/api/override/unset", json={"attr": "dhs_memory", "value": ""})
    assert response.status_code == 200 and response.json()["attr"] == "dhs_memory"


def test_api_next_breakpoint_returns_new_breakpoint(fake_sim_api):
    client, results = fake_sim_api
    results["next_breakpoint"] = {"success": True, "status": "moved_to_next_breakpoint",
                                  "breakpoint": {"name": "pass_2"}}
    response = client.post("/api/next-breakpoint")
    assert response.status_code == 200
    assert response.json()["breakpoint"]["name"] == "pass_2"

    results["start"] = {"success": True, "status": "started"}
    assert client.post("/api/start").status_code == 200
    results["admin_set_state"] = {"success": True}
    assert client.post("/api/admin/set-state", json={"attr": "dhs_memory", "value": "1"}).status_code == 200


def test_control_reports_commands_that_never_ran(fake_sim_api):
    client, results = fake_sim_api
    body = {"system": "ground_station", "control": "power_ul", "value": "60"}

    for never_ran in ({"success": False, "error": "Simulation is not running"},
                      {"success": False, "error": "Command timed out"}):
        results["control"] = never_ran
        response = client.post("/api/control", json=body)
        assert response.status_code == 400 and response.json()["detail"] == never_ran["error"]

    # a TC blocked on the ground is still an acknowledgement
    results["control"] = {"success": False, "status": "r:REL r:ACC r:EXE"}
    assert client.post("/api/control", json=body).json() == {"status": "r:REL r:ACC r:EXE"}
    results["control"] = {"success": True, "status": "OK"}
    assert client.post("/api/control", json=body).json() == {"status": "OK"}


def test_operators_cannot_set_internal_spacecraft_state(fake_sim_api):
    client, results = fake_sim_api
    results["control"] = {"success": True, "status": "g:REL g:ACC g:EXE"}
    results["tc_stack_push"] = {"success": True}
    user = {"X-User-Password": "user-pw", "X-Admin-Password": ""}
    internal = {"system": "spacecraft", "command": "x", "control": "eps_battery_dod", "value": "nan"}

    assert client.post("/api/control", json=internal, headers=user).status_code == 403
    assert client.post("/api/tc-stack", json=internal, headers=user).status_code == 403
    assert client.post("/api/tc-stack/send", json=internal, headers=user).status_code == 403
    # the admin panel and trigger scripts still can
    assert client.post("/api/control", json=internal).status_code == 200

    catalogue = {**internal, "control": "aocs_mode", "value": "SUN"}
    assert client.post("/api/tc-stack", json=catalogue, headers=user).status_code == 200


def test_tc_stack_accepts_user_or_admin_password(fake_sim_api):
    client, results = fake_sim_api
    results["tc_stack_push"] = {"success": True}
    results["tc_stack_delete"] = {"success": True}
    results["tc_stack_execute"] = {"success": True, "status": "g:REL g:ACC g:EXE", "command": "TC_AOCS_001"}
    tc = {"system": "spacecraft", "command": "TC_AOCS_001", "control": "aocs_mode", "value": "SUN"}
    user = {"X-User-Password": "user-pw", "X-Admin-Password": ""}
    nobody = {"X-User-Password": "", "X-Admin-Password": ""}

    for headers in (user, {}):  # {}: the client's default admin password
        assert client.post("/api/tc-stack", json=tc, headers=headers).status_code == 200
        assert client.post("/api/tc-stack/execute", headers=headers).status_code == 200
        assert client.delete("/api/tc-stack/0", headers=headers).status_code == 200
    assert client.post("/api/tc-stack", json=tc, headers=nobody).status_code == 401
    assert client.post("/api/tc-stack/execute", headers=nobody).status_code == 401
    assert client.delete("/api/tc-stack/0", headers=nobody).status_code == 401


def test_tc_stack_delete_out_of_range(fake_sim_api):
    client, results = fake_sim_api
    results["tc_stack_delete"] = {"success": False, "error": "No TC at index 3 (stack has 0)"}
    response = client.delete("/api/tc-stack/3")
    assert response.status_code == 400 and response.json()["detail"] == results["tc_stack_delete"]["error"]


def test_tc_send(fake_sim_api):
    client, results = fake_sim_api
    user = {"X-User-Password": "user-pw", "X-Admin-Password": ""}
    tc = {"system": "spacecraft", "command": "UP: fd > x", "control": "dhs_uploaded", "value": "fd > x"}

    results["tc_send"] = {"success": True, "status": "g:REL g:ACC g:EXE", "command": "UP: fd > x"}
    response = client.post("/api/tc-stack/send", json=tc, headers=user)
    assert response.status_code == 200
    assert response.json() == {"status": "g:REL g:ACC g:EXE", "command": "UP: fd > x"}
    results["tc_send"] = {"success": False, "error": "Simulation is not running"}
    assert client.post("/api/tc-stack/send", json=tc, headers=user).status_code == 400


def test_breakpoint_setup_is_instructor_only():
    from so.api import user_view, admin_view, public_scenario
    bp = {"name": "pass_1", "begin": "b", "end": "e", "ground_station": None,
          "sc_initial_state": {"eps_acu": "control_err"}, "gs_initial_state": {"carrier_ul": "off"}}
    data = {"type": "state", "scenario": {"name": "s", "breakpoints": [bp]}, "breakpoint": bp,
            "spacecraft": None, "spacecraft_admin": {"ts": 1}}

    for view in (user_view(data), {"scenario": public_scenario(data["scenario"])}):
        assert "control_err" not in str(view)
    assert user_view(data)["breakpoint"]["name"] == "pass_1"
    assert admin_view(data)["scenario"]["breakpoints"][0]["sc_initial_state"] == {"eps_acu": "control_err"}


def test_scenario_endpoints_hide_setup(fake_sim_api):
    client, results = fake_sim_api
    results["get_scenario"] = {"name": "s", "breakpoints": [{"name": "pass_1", "sc_initial_state": {"a": 1}}]}

    public = client.get("/api/scenario", headers={"X-Admin-Password": ""}).json()
    assert public["breakpoints"] == [{"name": "pass_1"}]
    assert client.get("/api/scenario").json() == results["get_scenario"]
    assert client.get("/api/scenarios", headers={"X-Admin-Password": ""}).status_code == 401
    assert client.get("/api/state", headers={"X-Admin-Password": ""}).status_code == 401
    assert client.get("/api/state", headers={"X-User-Password": "user-pw"}).status_code == 200
