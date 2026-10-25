#!/bin/sh
# Build a release zip from a git tag (tags are plain X.Y.Z, no "v" prefix).
# Only files tracked at that tag are included, minus anything marked
# export-ignore in .gitattributes.
#
#   sh bin/release.sh            package the tag matching the current VERSION
#   sh bin/release.sh X.Y.Z      package tag X.Y.Z
#
# Output: dist/sim-ops-ng-X.Y.Z.zip (unzips into sim-ops-ng-X.Y.Z/) and
#         dist/sim-ops-ng-X.Y.Z-notes.md (that version's CHANGELOG.md section)
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

tag=${1:-$(tr -d '[:space:]' < VERSION)}

echo "$tag" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || { echo "invalid tag: $tag (expected X.Y.Z)" >&2; exit 1; }
git rev-parse -q --verify "refs/tags/$tag" > /dev/null || { echo "tag $tag does not exist (create it with: git tag $tag)" >&2; exit 1; }

tagged_version=$(git show "$tag:VERSION" | tr -d '[:space:]')
[ "$tagged_version" = "$tag" ] || { echo "VERSION at tag $tag is '$tagged_version', expected '$tag'" >&2; exit 1; }

name="sim-ops-ng-$tag"
mkdir -p dist

# Release notes: the body of the "## X.Y.Z ..." section of CHANGELOG.md at the tag
git show "$tag:CHANGELOG.md" \
    | awk -v v="$tag" '/^## / { found = ($2 == v); next } found' \
    | sed -e '/./,$!d' > "dist/$name-notes.md"
grep -q . "dist/$name-notes.md" || { echo "no '## $tag' section in CHANGELOG.md at tag $tag" >&2; exit 1; }

git archive --format=zip --prefix="$name/" -o "dist/$name.zip" "$tag"
echo "dist/$name.zip"
echo "dist/$name-notes.md"
