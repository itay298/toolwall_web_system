#!/usr/bin/env bash
set -e
echo "=== אתחול מערכת פיקוח קיר כלים (Web Edition) ==="
python manage.py makemigrations inventory audit
python manage.py migrate
mkdir -p media/calibration media/anchors media/tools_ref media/audits
echo "=== מפעיל שרת בכתובת http://127.0.0.1:8000 ==="
python manage.py runserver
