#!/bin/bash
cd "$(dirname "$0")/backend"
source venv/bin/activate
echo "Starting Celery worker..."
echo "Make sure Redis is running: redis-server"
celery -A core worker --loglevel=info
