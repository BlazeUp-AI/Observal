#!/bin/sh
set -e

echo "Running database migrations..."
/app/.venv/bin/python -m alembic upgrade head

echo "Starting server..."
exec /app/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
