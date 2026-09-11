#!/bin/sh
# Entrypoint for the backend container: apply migrations, then start the API.
# Waiting for Postgres itself is handled by compose's `depends_on: condition:
# service_healthy`, so this only needs to run the app's own startup steps.
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting API server on port ${BACKEND_PORT:-8000} with ${UVICORN_WORKERS:-2} worker(s)..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${BACKEND_PORT:-8000}" \
    --workers "${UVICORN_WORKERS:-2}" \
    --proxy-headers \
    --forwarded-allow-ips '*'
