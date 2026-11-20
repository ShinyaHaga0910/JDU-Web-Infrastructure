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
url="https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/$ref/development/01_roles/cyber_security/tools/web_lab_bootstrap/classroom.py"
installer=$(mktemp)
trap 'rm -f -- "$installer"' EXIT

curl -q -fsS --proto '=https' "$url" -o "$installer"
python3 -B "$installer" "$@" --ref "$ref"
