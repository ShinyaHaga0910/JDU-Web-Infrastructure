#!/usr/bin/env bash
set -euo pipefail

# Resolve main once so a push during setup cannot mix versions.
repo='https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure.git'
head=$(git ls-remote --exit-code "$repo" refs/heads/main)
ref=${head%%$'\t'*}
[[ "$ref" =~ ^[a-f0-9]{40}$ ]]
url="https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/$ref/development/01_roles/cyber_security/tools/web_lab_bootstrap/classroom.py"
installer=$(mktemp)
trap 'rm -f -- "$installer"' EXIT

curl -q -fsS --proto '=https' "$url" -o "$installer"
python3 -B "$installer" "$@" --ref "$ref"
