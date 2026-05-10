#!/bin/sh
set -e

# Use Azure PostgreSQL by default if DATABASE_URL is not set externally
DATABASE_URL="${DATABASE_URL:-postgresql://Admin123:%40Password123@grf-ldp.postgres.database.azure.com:5432/ldp}"
export DATABASE_URL

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 120 --worker-class sync config.wsgi:application
