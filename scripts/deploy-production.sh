#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 scripts/check-release.py .env.production
# Migration failures stop API startup, rather than silently initializing the wrong schema.
docker compose --env-file .env.production -f compose.prod.yml up -d --build
printf '\nInspect status: docker compose --env-file .env.production -f compose.prod.yml ps\n'
printf 'Check HTTPS at your configured site and verify email signup manually.\n'
