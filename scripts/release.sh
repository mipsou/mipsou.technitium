#!/usr/bin/env bash
#
# release.sh — cut a release of the mipsou.technitium collection.
#
# Usage:
#   ./scripts/release.sh 0.1.0
#
# Prerequisites (install once on the release host):
#   pip install --user ansible-core antsibull-changelog
#   export GALAXY_API_KEY=<token from https://galaxy.ansible.com/ui/token/>
#
# The script:
#   1. Builds CHANGELOG.rst from changelogs/fragments/ via antsibull-changelog
#   2. Commits the changelog
#   3. Tags the release
#   4. Builds the collection tarball
#   5. Optionally publishes to Galaxy when GALAXY_API_KEY is set

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <version>" >&2
  exit 64
fi

VERSION="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "error: working tree is dirty — commit or stash first." >&2
  exit 1
fi

# 1. Sync galaxy.yml version with the requested one.
if ! grep -qE "^version:\s*${VERSION}\s*$" galaxy.yml; then
  echo "error: galaxy.yml version does not match ${VERSION} — update it first." >&2
  exit 1
fi

# 2. Assemble fragments into CHANGELOG.rst + changelogs/changelog.yaml.
antsibull-changelog release --version "${VERSION}"

# 3. Commit + tag.
git add CHANGELOG.rst changelogs/changelog.yaml changelogs/fragments
if [[ -n "$(git status --porcelain CHANGELOG.rst changelogs/)" ]]; then
  git commit -m "Release ${VERSION}"
fi
git tag -a "${VERSION}" -m "Release ${VERSION}"

# 4. Build.
rm -f mipsou-technitium-*.tar.gz
ansible-galaxy collection build --force

TARBALL="mipsou-technitium-${VERSION}.tar.gz"
if [[ ! -f "${TARBALL}" ]]; then
  echo "error: expected ${TARBALL} after build, not found." >&2
  exit 1
fi
echo "Built ${TARBALL}"

# 5. Publish, if a token is available. Otherwise stop after the build so the
#    operator can inspect the tarball before pushing.
if [[ -n "${GALAXY_API_KEY:-}" ]]; then
  ansible-galaxy collection publish "${TARBALL}" --api-key "${GALAXY_API_KEY}"
  echo "Published ${TARBALL} to Galaxy."
  echo "Next: git push --follow-tags"
else
  echo "GALAXY_API_KEY not set — skipping galaxy publish."
  echo "To publish: ansible-galaxy collection publish ${TARBALL} --api-key <token>"
fi
