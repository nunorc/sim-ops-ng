import json
import socket
import threading

import pytest

from conftest import free_port, wait_for


# ---- Sim <-> API socket ----

@pytest.fixture
def echo_server():
    from so.communication import SocketServer
    server = SocketServer(port=free_port())
    server.register_handler("echo", lambda params: params)
    server.start()
    assert wait_for(lambda: server._server_socket is not None)
    yield server
    server.stop()


@pytest.fixture
def client_for():
    from so.communication import SocketClient
    clients = []

    def _make(port, **kwargs):
        client = SocketClient(port=port, **kwargs)
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.disconnect()


def test_concurrent_and_large_commands(echo_server, client_for):
    client = client_for(echo_server.port)
    client.start()

    big = "x" * 200_000  # far over one recv()
    results = {}

    def send(i):
        results[i] = client.send_command("echo", {"i": i, "blob": big if i % 3 == 0 else ""})

    threads = [threading.Thread(target=send, args=(i,)) for i in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for i in range(30):
        assert results[i]["success"], results[i]
        assert results[i]["data"]["i"] == i
        assert len(results[i]["data"]["blob"]) == (len(big) if i % 3 == 0 else 0)


def test_coalesced_commands_all_answered(echo_server):
    with socket.create_connection(("127.0.0.1", echo_server.port), timeout=5) as sock:
        payload = b"".join(
            (json.dumps({"type": "command", "id": i, "command": "echo", "params": {"i": i}}) + "\n").encode()
            for i in range(5)
        )
        sock.sendall(payload)  # one write, several messages

        buffer = b""
        while buffer.count(b"\n") < 5:
            buffer += sock.recv(65536)
        ids = sorted(json.loads(line)["id"] for line in buffer.split(b"\n") if line)
        assert ids == [0, 1, 2, 3, 4]


def test_client_resubscribes_when_sim_starts_late(client_for):
    from so.communication import SocketServer

    port = free_port()
    states = []
    client = client_for(port, retry_interval=0.1)
    client.register_broadcast_handler("state", states.append)
    client.start()  # nothing listening yet
    assert not client.is_connected()

    server = SocketServer(port=port)
    server.set_on_subscribe(lambda: server.broadcast({"type": "state", "n": 1}))
    server.start()
    try:
        # no command sent: the background loop connects and the subscribe snapshot arrives
        assert wait_for(lambda: states, timeout=5)
        assert states[0]["n"] == 1

        # sim restart: reconnect again without any command
        server.stop()
        assert wait_for(lambda: not client.is_connected())
        server = SocketServer(port=port)
        server.set_on_subscribe(lambda: server.broadcast({"type": "state", "n": 2}))
        server.start()
        assert wait_for(lambda: states[-1]["n"] == 2, timeout=5)
    finally:
        server.stop()
