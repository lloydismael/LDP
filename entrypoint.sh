#!/bin/sh
set -e

# Never embed production credentials in an image. Local development falls back
# to a persistent SQLite mount; Azure deployments must supply DATABASE_URL.
DATABASE_URL="${DATABASE_URL:-sqlite:////app/data/db.sqlite3}"
export DATABASE_URL

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

APP_PORT=8001
echo "Starting gunicorn on fixed port ${APP_PORT}..."
exec gunicorn --bind "0.0.0.0:${APP_PORT}" --workers 3 --timeout 120 --worker-class sync config.wsgi:application
