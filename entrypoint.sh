#!/bin/bash
set -e

cd /app/net_admin

# Migration은 초기화 시에만 (파일 존재 확인)
if [ ! -f "/tmp/.migrations_done" ]; then
    echo "[STARTUP] Running migrations..."
    python manage.py migrate
    touch /tmp/.migrations_done
    echo "[STARTUP] Migrations completed"
else
    echo "[STARTUP] Skipping migrations (already done)"
fi

# Static files 수집 (매번 실행)
echo "[STARTUP] Collecting static files..."
python manage.py collectstatic --noinput || true
echo "[STARTUP] Static files collected"

# Gunicorn 시작
echo "[STARTUP] Starting Gunicorn..."
exec gunicorn net_admin.wsgi:application \
    --bind 0.0.0.0:8080 \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
