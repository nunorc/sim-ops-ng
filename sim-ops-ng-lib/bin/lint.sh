#!/bin/sh
# pylint over the package, entry points and tests (run from sim-ops-ng-lib; CI runs this too)
set -e

uv run pylint so bin

# pytest idioms: fixtures as arguments, imports inside tests, tests reaching into internals
uv run pylint tests \
    --disable=import-outside-toplevel,protected-access,redefined-outer-name,unused-argument
