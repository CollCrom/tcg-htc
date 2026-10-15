#!/usr/bin/env bash
# Runs actionlint over .github/workflows/ with the version CI pins. The first run
# downloads the binary into a gitignored cache; later runs reuse it. Extra
# arguments go to actionlint, e.g. a workflow file to lint instead of the folder.
set -euo pipefail

version=1.7.7
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cache="${ACTIONLINT_CACHE_DIR:-$root/.cache/actionlint}/$version"
bin="$cache/actionlint"

if [ ! -x "$bin" ]; then
  mkdir -p "$cache"
  bash <(curl -sSfL "https://raw.githubusercontent.com/rhysd/actionlint/v$version/scripts/download-actionlint.bash") "$version" "$cache"
fi

# Colour only where it renders: a terminal, or the GitHub Actions log.
if [ -t 1 ] || [ -n "${GITHUB_ACTIONS:-}" ]; then
  set -- -color "$@"
fi

cd "$root"
exec "$bin" "$@"
