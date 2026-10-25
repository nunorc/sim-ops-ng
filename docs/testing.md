---
title: "Testing and linting"
weight: 30
---

# Testing and linting

---

## 1. Backend

```sh
$ cd sim-ops-ng-lib
$ uv run pytest -v
$ sh bin/lint.sh      # pylint: so, bin and tests
```

Tests live in [`sim-ops-ng-lib/tests/`](../sim-ops-ng-lib/tests/).

---

## 2. Frontends

```sh
$ cd sim-ops-ng-mcs
$ npm run lint         # ESLint, with --fix
$ npm run typecheck    # vue-tsc -b
$ npm run test:unit    # Vitest, tests in src/**/__tests__/
$ npm run build        # type check + production build

$ cd sim-ops-ng-3dv
$ npm run lint
$ npm test             # Vitest, tests in src/__tests__/
$ npm run build        # tsc + production build
```

---

## 3. CI

GitHub Actions in [`.github/workflows/`](../.github/workflows/), each triggered by its own paths;
every step blocks.

| Workflow | Runs |
|---|---|
| `sim-ops-ng-lib-test-and-lint.yml` | `uv sync --locked`, `bin/lint.sh` (pylint over `so`, `bin` and `tests`), `pytest -v` |
| `sim-ops-ng-mcs-lint-and-build.yml` | `npm ci`, `eslint`, `npm run typecheck`, `npm run test:unit`, `vite build` |
| `sim-ops-ng-3dv-lint-and-build.yml` | `npm ci`, `eslint`, `npm test`, `npm run build` (`tsc` + `vite build`) |
| `docker.yml` | `docker compose build`, then `up --wait` (every healthcheck must pass) and a smoke test through nginx; on any change outside `docs/` and `*.md` |
| `version-check.yml` | `sh bin/version.sh check` |
| `release.yml` | On a tag: runs the lib, mcs, 3dv and docker workflows first, see [releasing.md](releasing.md). |
| `docs.yml` | Builds these docs (Hugo, pinned) and publishes them to GitHub Pages. |

---

## 4. The docs

Plain markdown in [`docs/`](../docs/); [`docs/site/`](../docs/site/) builds a Hugo site with the
Hextra theme (submodule at `docs/site/themes/hextra`):

```sh
$ git submodule update --init
$ hugo server --config docs/site/hugo.toml     # from the repo root
```

A new page needs `title`/`weight` front matter and its filename added to one of the mounts in
`docs/site/hugo.toml`.
