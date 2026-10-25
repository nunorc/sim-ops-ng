---
title: "Deployment"
weight: 20
---

# Deployment

Docker Compose ([`docker-compose.yml`](../docker-compose.yml)), images from
[`containers/`](../containers/), build context the repo root.

```sh
$ docker compose build
$ docker compose up -d
```

---

## 1. Services

| Service | Image | Exposed | Notes |
|---|---|---|---|
| `sim-ops-ng-minio` | [`Dockerfile.minio`](../containers/Dockerfile.minio) | `9001` (console) | Object store for packets and products; data in the `minio-data` volume. |
| `sim-ops-ng-sim` | [`Dockerfile.lib`](../containers/Dockerfile.lib) | — | Engine; binds its socket on `0.0.0.0` inside the network. |
| `sim-ops-ng-api` | [`Dockerfile.lib`](../containers/Dockerfile.lib) | — | API. |
| `sim-ops-ng-admin` | [`Dockerfile.lib`](../containers/Dockerfile.lib) | — | Admin panel. |
| `sim-ops-ng-3dv` | [`Dockerfile.3dv`](../containers/Dockerfile.3dv) | — | 3D viewer; `VITE_CESIUM_TOKEN` is a build argument. |
| `sim-ops-ng-nginx` | [`Dockerfile.nginx`](../containers/Dockerfile.nginx) | `8080` | Builds the MCS and serves it, and proxies everything else. |

Only nginx (`8080`) and the MinIO console (`9001`, on `127.0.0.1` only) are published; everything
else is reached on the internal `sim-ops-net` network.

- **One Python image.** sim, api and admin share the `sim-ops-ng-lib` image (`uv`, from
  `uv.lock`, with `de421.bsp` baked in) and differ only in `command`.
- **MinIO is built from source** (no upstream images; `MINIO_RELEASE` pins it). The Go build needs
  ~2 GB: on a small Docker VM build it alone first (`docker compose build sim-ops-ng-minio`).
- **Healthchecks** gate startup: minio → sim → api → admin/3dv → nginx.
- **Non-root.** The Python services run as `simops` (uid 1000), MinIO as `minio` (uid 1000), and
  nginx/3dv use `nginx-unprivileged` (uid 101, listening on `8080` inside the container).

---

## 2. nginx

[`containers/nginx/nginx.conf`](../containers/nginx/nginx.conf) is the main config; routing is in
[architecture.md](architecture.md#5-nginx-routing).
[`containers/nginx/3dv.conf`](../containers/nginx/3dv.conf) serves the 3dv container.
