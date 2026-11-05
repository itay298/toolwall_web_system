@echo off
echo === Initializing Tool Wall Web System ===
.venv\Scripts\python.exe manage.py makemigrations inventory audit
.venv\Scripts\python.exe manage.py migrate
if not exist media\calibration mkdir media\calibration
if not exist media\anchors mkdir media\anchors
if not exist media\tools_ref mkdir media\tools_ref
if not exist media\audits mkdir media\audits
echo === Starting Django Server at http://127.0.0.1:8000 ===
.venv\Scripts\python.exe manage.py runserver
