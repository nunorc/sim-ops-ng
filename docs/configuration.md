---
title: "Configuration"
weight: 10
---

# Configuration

All configuration is environment variables in **one** root file, read by Docker Compose, the
Python apps (`load_dotenv()`) and the Vite frontends (`envDir`):

```sh
$ cp .env.example .env
```

[`.env.example`](../.env.example) is the full, commented list, set up for local dev. Under Docker
Compose, `docker-compose.yml` sets the networking variables (hosts, ports, MinIO endpoint, API URL).

| Variable | Default | Used by | Description |
|---|---|---|---|
| `SIM_OPS_NG_SCENARIO` | `data/demo.json` | sim | Scenario loaded at start. See [scenarios.md](scenarios.md). |
| `SIM_OPS_NG_SOCKET_HOST` | `127.0.0.1` | sim, api | Engine socket bind host / host the API connects to (`sim-ops-ng-sim` in compose). |
| `SIM_OPS_NG_SOCKET_PORT` | `5555` | sim, api | Engine socket port. |
| `SIM_OPS_NG_API_HOST` | `0.0.0.0` | api | API bind host. |
| `SIM_OPS_NG_API_PORT` | `9111` | api | API port. |
| `SIM_OPS_NG_API_URL` | `http://localhost:9111` | admin | Where the admin app reaches the API. |
| `SIM_OPS_NG_ADMIN_HOST` / `_PORT` / `_WORKERS` | `0.0.0.0` / `9131` / `4` | admin | gunicorn bind and workers. |
| `SIM_OPS_NG_ADMIN_PASSWORD` | `admin123` | api, admin | Instructor password. |
| `SIM_OPS_NG_USER_PASSWORD` | `user123` | api | Operator password (changeable at runtime). |
| `FLASK_SECRET_KEY` | random | admin | Signs the admin session cookie. If unset, admin logins end when the admin app restarts. |
| `SIM_OPS_NG_MINIO_ENDPOINT` | `localhost:9000` | sim, api | Object store (`sim-ops-ng-minio:9000` in compose). |
| `SIM_OPS_NG_MINIO_ROOT_USER` / `_PASSWORD` | `myusername` / `mypassword` | sim, api, minio | Object store credentials. |
| `VITE_CESIUM_TOKEN` | — | 3dv (build) | Cesium Ion token. |
| `VITE_SO_API`, `VITE_WS_URL` | same origin | mcs (dev only) | API and WebSocket URLs for `npm run dev`. The nginx build forces them empty. |
| `SIM_OPS_NG_WS_URL` | derived | admin | WebSocket URL the admin page connects to. |

The default passwords are for local use only: change them, and set `FLASK_SECRET_KEY`, before
exposing the stack to a network.
