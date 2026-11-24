#!/usr/bin/env bash
set -euo pipefail

# Published build artifacts replace the empty ref with their source commit.
ref=''
repo='https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure.git'
if [[ -z "$ref" ]]; then
  # Resolve main once so a push during setup cannot mix versions.
  head=$(git ls-remote --exit-code "$repo" refs/heads/main)
  ref=${head%%$'\t'*}
fi
[[ "$ref" =~ ^[a-f0-9]{40}$ ]]
if [[ "${1:-}" =~ ^portal-(prepare|connect|enable|approve|teacher)$ ]]; then
  portal_source=$(mktemp -d)
  trap 'rm -rf -- "$portal_source"' EXIT
  git -C "$portal_source" init -q
  git -C "$portal_source" remote add origin "$repo"
  git -C "$portal_source" config remote.origin.promisor true
  git -C "$portal_source" config remote.origin.partialclonefilter blob:none
  git -C "$portal_source" sparse-checkout set development/web_portal_poc development/01_roles/cyber_security/tools
  git -C "$portal_source" fetch -q --depth 1 --filter=blob:none origin "$ref"
  git -C "$portal_source" checkout -q --detach FETCH_HEAD
  if [[ "$1" == 'portal-prepare' || "$1" == 'portal-enable' ]]; then
    npm --prefix "$portal_source/development/web_portal_poc/web" ci --omit=dev --no-audit --no-fund
  fi
  python3 -B "$portal_source/development/web_portal_poc/deploy_classroom_portal.py" "$@" --ref "$ref"
  exit
fi

url="https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/$ref/development/01_roles/cyber_security/tools/web_lab_bootstrap/classroom.py"
installer=$(mktemp)
trap 'rm -f -- "$installer"' EXIT

curl -q -fsS --proto '=https' "$url" -o "$installer"
python3 -B "$installer" "$@" --ref "$ref"
