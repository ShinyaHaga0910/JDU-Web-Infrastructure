#!/usr/bin/env bash
set -euo pipefail

# Keep the installer and all files it downloads on the same classroom revision.
ref='1b5d55149d43383c63b013e8c159da559524bb0d'
sha256='d73eb490825b31f6bcc9c272673784055b7e2890ff13db58ec65e1ebb018237f'
url="https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/$ref/development/01_roles/cyber_security/tools/web_lab_bootstrap/classroom.py"
installer=$(mktemp)
trap 'rm -f -- "$installer"' EXIT

curl -q -fsS --proto '=https' "$url" -o "$installer"
printf '%s  %s\n' "$sha256" "$installer" | sha256sum --check --status
python3 -B "$installer" "$@" --ref "$ref"
