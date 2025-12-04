#!/bin/bash
cd "$(dirname "$0")/backend"
source venv/bin/activate
echo "Starting Django server on http://localhost:8000"
python manage.py runserver 8000
