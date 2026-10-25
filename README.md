
# sim-ops-ng

An environment for **spacecraft operations exercises**: a simulated spacecraft on a real orbit,
a ground station, and a Monitoring and Control System (MCS) where the Flight Control Team (FCT)
manages the spacecraft.
An admin panel is used by the instructor to manage the sessions.

Based on [Sim-Ops](https://github.com/nunorc/sim-ops).

![The MCS during a pass: dashboard, OM, ground station, SpaCon, TC history and the subsystem views](docs/images/mcs-slideshow.gif)

The documentation is available from **https://nunorc.github.io/sim-ops-ng/**, the source is in
[`docs/`](docs/) (start at [docs/index.md](docs/index.md)).

## Repository content

* `sim-ops-ng-lib/`: Python backend, package `so` (simulation engine, REST/WebSocket API and admin panel), managed with `uv`.
* `sim-ops-ng-mcs/`: MCS frontend (Vue 3 + TypeScript).
* `sim-ops-ng-3dv/`: 3D orbit viewer (TypeScript + CesiumJS).
* `containers/`: Dockerfiles and nginx config.
* `docs/`: the documentation; `docs/site/` holds the Hugo site.
* `bin/`: `version.sh` and `release.sh`.

See [docs/index.md](docs/index.md#2-repository-layout) for the full layout.

## Configuration

All configuration is environment variables in one root `.env` file, read by Docker Compose, the
Python apps and the Vite frontends:

```sh
$ cp .env.example .env
```

The defaults work locally. [`.env.example`](.env.example) is the full, commented list, set up for
running manually (everything on localhost); under Docker Compose, `docker-compose.yml` sets the
networking variables itself. Key variables:

| Variable | Default | Description |
|---|---|---|
| `SIM_OPS_NG_SCENARIO` | `data/demo.json` | Scenario loaded at start |
| `SIM_OPS_NG_SOCKET_HOST` / `_PORT` | `127.0.0.1` / `5555` | Engine socket |
| `SIM_OPS_NG_API_HOST` / `_PORT` | `0.0.0.0` / `9111` | API bind |
| `SIM_OPS_NG_ADMIN_PASSWORD` | `admin123` | Instructor password |
| `SIM_OPS_NG_USER_PASSWORD` | `user123` | Operator password |
| `FLASK_SECRET_KEY` | random | Signs the admin session cookie |

The default passwords are for local use only: change them, and set `FLASK_SECRET_KEY`, before
exposing the stack to a network. See [docs/configuration.md](docs/configuration.md) for every
variable.

## Running Using Docker

```sh
$ docker compose build
$ docker compose up -d
```

| URL | What | Password |
|---|---|---|
| http://localhost:8080 | MCS | `SIM_OPS_NG_USER_PASSWORD` (default `user123`) |
| http://localhost:8080/admin | Admin panel | `SIM_OPS_NG_ADMIN_PASSWORD` (default `admin123`) |
| http://localhost:8080/3dv | 3D viewer | — |

The simulation starts **stopped**: start it from the admin panel. The first build compiles MinIO
from source (a few minutes, ~2 GB of memory). See [docs/deployment.md](docs/deployment.md).

## Running Manually

`.env.example` already points everything at localhost. One terminal per service:

```sh
$ cd sim-ops-ng-lib
$ export PYTHONPATH=.

$ uv run bin/sim-ops.py        # sim engine, socket on :5555
$ uv run bin/sim-ops-api.py    # REST/WebSocket API on :9111
$ uv run bin/admin.py          # admin panel on :9131

$ sh bin/run-devel.sh          # ...or all three in one screen session
```

On first use skyfield downloads `de421.bsp` (~17 MB) into `sim-ops-ng-lib/`. MinIO is optional:
without it, packets and flight-dynamics products aren't stored.

MCS (set `VITE_SO_API` and `VITE_WS_URL` in `.env`):

```sh
$ cd sim-ops-ng-mcs
$ npm install
$ npm run dev
```

See [docs/quickstart.md](docs/quickstart.md) for a first pass through an exercise.

## Testing and Linting

Backend:

```sh
$ cd sim-ops-ng-lib
$ uv run pytest -v
$ sh bin/lint.sh      # pylint: so, bin and tests
```

Frontends:

```sh
$ cd sim-ops-ng-mcs
$ npm run lint         # ESLint, with --fix
$ npm run typecheck    # vue-tsc -b
$ npm run test:unit    # Vitest
$ npm run build        # type check + production build

$ cd sim-ops-ng-3dv
$ npm run lint
$ npm test             # Vitest
$ npm run build        # tsc + production build
```

CI (GitHub Actions) runs all of these, every step blocking, plus a `docker compose` build and smoke
test. See [docs/testing.md](docs/testing.md).

## Versioning

The root `VERSION` file is the source of truth, mirrored in `sim-ops-ng-lib/pyproject.toml`,
`so/__init__.py` and the MCS and 3DV `package.json`. Change it only with `bin/version.sh`:

```sh
$ sh bin/version.sh              # print the current version
$ sh bin/version.sh check        # verify every component matches VERSION (CI runs this)
$ sh bin/version.sh set 0.1.0    # bump everything, and refresh the lock files
```

It is served at `/api/version`; the MCS and 3DV bake it in at build time and show it in their
headers.

## Releasing

1. Move the `## Unreleased` notes in `CHANGELOG.md` under a new `## X.Y.Z - YYYY-MM-DD` heading.
2. `sh bin/version.sh set X.Y.Z`, then commit.
3. `git tag X.Y.Z && git push origin X.Y.Z` — plain `X.Y.Z`, no `v` prefix.

Pushing the tag runs the lib, mcs, 3dv and docker workflows and then publishes a GitHub release
with the source zip and that changelog section as its notes. `sh bin/release.sh X.Y.Z` builds the
same zip and notes locally in `dist/`. See [docs/releasing.md](docs/releasing.md).

## Acknowledgements

Thanks to David Evans for the help and contributions with the design and behaviour of the
simulator, and to the
[Sim-Ops](https://github.com/nunorc/sim-ops) team.

MCS UI theme based on HUD Vue by Sean Ngu.

## License

Released under the MIT License, see [LICENSE](LICENSE).
