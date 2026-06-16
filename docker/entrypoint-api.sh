#!/bin/sh
set -e
cd /app/knowmind-server
echo "Running alembic upgrade head..."
alembic upgrade head
echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
