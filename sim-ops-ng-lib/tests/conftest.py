"""Fixtures and helpers shared by the test modules (helpers are imported as `from conftest import ...`)."""
import base64
import socket
import time

import pytest


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def ws_protocols(password):
    token = base64.urlsafe_b64encode(password.encode()).decode().rstrip("=")
    return ["sim-ops", f"sim-ops.password.{token}"]


@pytest.fixture
def no_minio(monkeypatch):
    """Point the object store at a closed local port, i.e. MinIO down."""
    from so.core import ObjectStore
    monkeypatch.setattr(ObjectStore.__init__, "__defaults__", ("127.0.0.1:1", "user", "password"))


@pytest.fixture
def sim(monkeypatch, no_minio):
    """SimOps on data/demo.json (not running), its socket server on a free port."""
    from so.core import SimOps
    monkeypatch.setenv("SIM_OPS_NG_SOCKET_PORT", str(free_port()))
    sim = SimOps(scenario="data/demo.json")
    yield sim
    sim.shutdown()


@pytest.fixture
def offline_api(monkeypatch, no_minio):
    """(SimOpsAPI, TestClient) with no sim listening on its port: commands fail, but auth is checked first."""
    from fastapi.testclient import TestClient
    from so.api import SimOpsAPI
    monkeypatch.setenv("SIM_OPS_NG_USER_PASSWORD", "user-pw")
    monkeypatch.setenv("SIM_OPS_NG_ADMIN_PASSWORD", "admin-pw")
    api = SimOpsAPI(simops_port=free_port())
    with TestClient(api.api) as client:
        yield api, client
