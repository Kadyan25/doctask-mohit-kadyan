#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

docker compose up --build -d

echo ""
echo "Backend applies migrations automatically on startup (see backend/entrypoint.sh)."
echo "Waiting a few seconds for everything to come up..."
sleep 5

echo ""
echo "Ready:"
echo "  Frontend:  http://localhost:5173"
echo "  Backend:   http://localhost:8000"
echo "  API docs:  http://localhost:8000/docs"
echo ""
echo "Logs: docker compose logs -f"
