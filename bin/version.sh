#!/bin/sh
# Project-wide version management. The root VERSION file is the single source
# of truth; lib, mcs and 3dv all carry the same version.
#
#   sh bin/version.sh              print the current version
#   sh bin/version.sh check        verify every component matches VERSION
#   sh bin/version.sh set X.Y.Z    write X.Y.Z to VERSION and all components
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

current() { tr -d '[:space:]' < VERSION; }

pkg_version() { sed -n 's/^  "version": "\(.*\)",$/\1/p' "$1/package.json"; }

check() {
    want=$(current)
    status=0
    for got in \
        "sim-ops-ng-lib/pyproject.toml:$(sed -n 's/^version = "\(.*\)"$/\1/p' sim-ops-ng-lib/pyproject.toml)" \
        "sim-ops-ng-lib/so/__init__.py:$(sed -n "s/^__version__ = '\(.*\)'$/\1/p" sim-ops-ng-lib/so/__init__.py)" \
        "sim-ops-ng-mcs/package.json:$(pkg_version sim-ops-ng-mcs)" \
        "sim-ops-ng-3dv/package.json:$(pkg_version sim-ops-ng-3dv)"
    do
        file=${got%%:*}
        ver=${got#*:}
        if [ "$ver" != "$want" ]; then
            echo "MISMATCH $file: '$ver' (VERSION is '$want')" >&2
            status=1
        fi
    done
    [ $status -eq 0 ] && echo "all components at $want"
    return $status
}

set_version() {
    new=$1
    echo "$new" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || { echo "invalid version: $new (expected X.Y.Z)" >&2; exit 1; }

    echo "$new" > VERSION
    sed -i.bak "s/^version = \".*\"$/version = \"$new\"/" sim-ops-ng-lib/pyproject.toml
    sed -i.bak "s/^__version__ = '.*'$/__version__ = '$new'/" sim-ops-ng-lib/so/__init__.py
    rm -f sim-ops-ng-lib/pyproject.toml.bak sim-ops-ng-lib/so/__init__.py.bak
    (cd sim-ops-ng-lib && uv lock --quiet)
    for app in sim-ops-ng-mcs sim-ops-ng-3dv; do
        (cd "$app" && npm version "$new" --no-git-tag-version --allow-same-version > /dev/null)
    done

    check
}

case "${1:-}" in
    "")    echo "$(current)" ;;
    check) check ;;
    set)   [ $# -eq 2 ] || { echo "usage: $0 set X.Y.Z" >&2; exit 1; }; set_version "$2" ;;
    *)     echo "usage: $0 [check | set X.Y.Z]" >&2; exit 1 ;;
esac
