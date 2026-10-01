#!/usr/bin/env sh
set -e

# Ensure export dir exists
mkdir -p /app/exports || true

# If running as root, fix perms on the mounted volume
if [ "$(id -u)" = "0" ]; then
  chmod 0777 /app/exports 2>/dev/null || true
else
  # Not root; if not writable, we warn and you can choose to fall back to /tmp
  if [ ! -w /app/exports ]; then
    echo "WARN: /app/exports not writable; consider one-time: docker exec -u 0 <ctr> sh -lc 'chmod 0777 /app/exports'" >&2
  fi
fi

if [ $# -gt 0 ]; then
  exec "$@"
fi

# Run migrations before starting the app so the schema is always up to date.
# Uses the DATABASE_URL env var set by docker-compose (points to atlasdb).
echo "Running Alembic migrations..."
(cd /backend && alembic upgrade head)

exec python3 /app/api/app.py
