#!/bin/sh
set -e

# A command given to the image runs instead of the web app: the stats-worker
# service runs `python -m app.jobs.daily_refresh` (no migrations, no server).
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

echo "=== Running Alembic migrations ==="
alembic upgrade head
echo "=== Migrations complete ==="

echo "=== Testing app import ==="
python -c "from app.main import app; print('Import OK')" || echo "IMPORT FAILED"

echo "=== Starting uvicorn on port ${PORT:-8001} ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8001}" --log-level debug
