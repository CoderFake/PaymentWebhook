#!/bin/bash

set -e

echo "Waiting for PostgreSQL..."
until pg_isready -h db -p 5432 -U admin; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done
echo "PostgreSQL is up!"

echo "Running migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn with 6 workers..."
exec gunicorn PaymentWebhook.wsgi:application --bind 0.0.0.0:8000 --workers 6

