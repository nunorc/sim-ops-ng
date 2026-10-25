# Changelog

All notable changes to this project are documented here. Each release has a
`## X.Y.Z - YYYY-MM-DD` section, and its body becomes the GitHub release notes.
Collect changes under `## Unreleased` and rename it when cutting a release.

## 0.0.1 - 2026-10-25

Initial release.

- Simulation engine and REST/WebSocket API (`sim-ops-ng-lib`)
- Mission Control System frontend (`sim-ops-ng-mcs`)
- 3D visualization (`sim-ops-ng-3dv`)
- Docker Compose setup for the full stack
- Single project version (`VERSION`), exposed at `/api/version` and shown in the MCS and 3DV headers
- Documentation site: markdown in `docs/`, built with Hugo + Hextra and published to GitHub Pages
