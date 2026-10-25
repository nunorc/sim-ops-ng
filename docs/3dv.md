---
title: "3DV — 3D visualization"
weight: 30
---

# 3DV — 3D visualization

A CesiumJS view of the spacecraft in orbit and the ground station, in
[`sim-ops-ng-3dv/`](../sim-ops-ng-3dv/): the scene in [`src/main.ts`](../sim-ops-ng-3dv/src/main.ts),
with unit-tested helpers in [`src/geometry.ts`](../sim-ops-ng-3dv/src/geometry.ts) and
[`src/format.ts`](../sim-ops-ng-3dv/src/format.ts).
Served at `/3dv/` behind nginx.

---

## 1. Data

Reads the password-less, read-only `/api/ws/viewer` WebSocket. It ignores link state, so the
orbit moves without `FRAME_LOCK`. Draws the current breakpoint's ground station; reconnects with a
1 s → 15 s back-off.

---

## 2. What it shows

- The spacecraft — bus, solar panels, antenna — oriented along its pointing target (Sun or nadir).
- The ground station dish.
- Uplink and downlink as animated "wave" lines between them, following the link state.

---

## 3. Build

```sh
$ cd sim-ops-ng-3dv
$ npm install
$ npm run dev
$ npm run build
$ npm run lint
```

`VITE_CESIUM_TOKEN` (Cesium Ion) is baked in at build time; Docker passes it from `.env` as a
build argument.
