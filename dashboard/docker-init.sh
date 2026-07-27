#!/usr/bin/env bash
# One-shot bootstrap: install local drivers, then prepare the metadata DB.
set -euo pipefail

REQ="/app/docker/requirements-local.txt"
if [ -f "$REQ" ]; then
  echo "==> Installing local driver requirements ($REQ)..."
  uv pip install --no-cache-dir -r "$REQ"
fi

echo "==> Upgrading Superset metadata database..."
superset db upgrade

echo "==> Creating admin user (idempotent)..."
superset fab create-admin \
  --username "${ADMIN_USERNAME:-admin}" \
  --firstname "${ADMIN_FIRSTNAME:-Superset}" \
  --lastname "${ADMIN_LASTNAME:-Admin}" \
  --email "${ADMIN_EMAIL:-admin@example.com}" \
  --password "${ADMIN_PASSWORD:-admin}" || true

echo "==> Initializing roles and permissions..."
superset init

echo "==> Bootstrap complete."
