
# sim-ops-ng-lib

The Python backend of [Sim-Ops NG](../README.md): the simulation engine, the REST/WebSocket API and
the admin panel. The three run as separate processes: the API talks to the engine over a TCP
socket, and the admin panel goes through the API.

| Entry point | Process | Port |
|---|---|---|
| `bin/sim-ops.py` | Simulation engine (`so/core.py`) | `5555` (socket) |
| `bin/sim-ops-api.py` | REST/WebSocket API (`so/api.py`, FastAPI) | `9111` |
| `bin/admin.py` | Admin panel (`so/admin.py`, Flask + gunicorn) | `9131` |

Layout:

* `so/`: the `so` package. `core.py` owns the sim loop, `spacecraft.py` and `ground_station.py`
  the two simulated sides, `sys/` the spacecraft subsystems (AOCS, TTC, EPS, DHS, Payload),
  `rf_link.py` the link budget, `data_model.py` the state dataclasses and `communication.py` the
  engine socket.
* `data/`: scenarios (`demo.json`, `testing.json`) and trigger scripts.
* `tests/`: pytest suite.
* `bin/`: the entry points above, plus `run-devel.sh` (all three in a screen session) and
  `ws-client.py` (prints the API's WebSocket feed).

## Running

Dependencies are managed with [uv](https://github.com/astral-sh/uv). Configuration comes from the
`.env` at the repository root (see [configuration](../docs/configuration.md)).

```sh
$ cd sim-ops-ng-lib
$ export PYTHONPATH=.

$ uv run bin/sim-ops.py        # engine
$ uv run bin/sim-ops-api.py    # API (separate terminal)
$ uv run bin/admin.py          # admin panel (separate terminal)
```

On first use skyfield downloads the `de421.bsp` ephemeris (about 17 MB) from JPL into this
directory. MinIO is optional: without it the engine keeps running, and TM/TC packets and
products are only stored while it is reachable.

## Testing

```sh
$ uv run pytest -v
$ sh bin/lint.sh      # pylint: so, bin and tests
```

More in the [documentation](https://nunorc.github.io/sim-ops-ng/) (source in [`docs/`](../docs/)).
