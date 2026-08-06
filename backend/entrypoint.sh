#!/usr/bin/env bash
set -e

echo "Applying migrations (retrying until the database accepts connections)..."
# `python -m alembic` (not the bare `alembic` console script) so the cwd (/app,
# containing the app/ package) is added to sys.path — env.py imports app.config.
until python -m alembic upgrade head; do
  echo "Database not ready yet, retrying in 2s..."
  sleep 2
done

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
