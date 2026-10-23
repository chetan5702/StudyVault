#!/usr/bin/env bash
# Consistent logical PostgreSQL + uploaded files snapshot during a write freeze.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ ! -f .env.production ]]; then echo 'Missing .env.production' >&2; exit 1; fi
compose=(docker compose --env-file .env.production -f compose.prod.yml)
mkdir -p backups
chmod 700 backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -m 700 "backups/$stamp"
restore_services() { "${compose[@]}" start api worker >/dev/null || true; }
trap restore_services EXIT
"${compose[@]}" stop api worker
"${compose[@]}" exec -T postgres pg_dump -U studyvault -d studyvault -Fc > "backups/$stamp/database.dump"
docker run --rm --mount type=volume,source=studyvault_uploads,target=/data,readonly --mount "type=bind,source=$(pwd)/backups/$stamp,target=/backup" alpine:3.20 sh -c 'cd /data && tar -czf /backup/uploads.tar.gz .'
(cd "backups/$stamp" && sha256sum database.dump uploads.tar.gz > SHA256SUMS)
trap - EXIT
restore_services
echo "Backup created at backups/$stamp. Copy encrypted archives OFF the server and test restoration."
