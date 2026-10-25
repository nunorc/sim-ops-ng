---
title: "Versioning and releases"
weight: 40
---

# Versioning and releases

---

## 1. One version

The root [`VERSION`](../VERSION) file is the source of truth, mirrored in
`sim-ops-ng-lib/pyproject.toml`, `so/__init__.py` and the MCS and 3DV `package.json`. Change it
only with [`bin/version.sh`](../bin/version.sh):

```sh
$ sh bin/version.sh              # print the current version
$ sh bin/version.sh check        # verify every component matches VERSION (CI runs this)
$ sh bin/version.sh set 0.1.0    # bump everything, and refresh the lock files
```

It is served at `/api/version`; the MCS and 3DV bake it in at build time (`__APP_VERSION__`).

---

## 2. Cutting a release

1. Move the `## Unreleased` notes in [`CHANGELOG.md`](../CHANGELOG.md) under a new
   `## X.Y.Z - YYYY-MM-DD` heading.
2. `sh bin/version.sh set X.Y.Z`, then commit.
3. `git tag X.Y.Z && git push origin X.Y.Z` — plain `X.Y.Z`, no `v` prefix.

The tag runs [`release.yml`](../.github/workflows/release.yml): after the lib, mcs, 3dv and docker
workflows pass, [`bin/release.sh`](../bin/release.sh) builds `dist/sim-ops-ng-X.Y.Z.zip` (a `git
archive` of the tag minus [`.gitattributes`](../.gitattributes) `export-ignore` paths) and a GitHub
release is published with the changelog section as notes (missing section = failure). Build the zip
locally with `sh bin/release.sh X.Y.Z`.
