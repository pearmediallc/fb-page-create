#!/bin/bash
# Start all services for the Page Generator project

echo "=== Page Generator Project ==="
echo ""
echo "Prerequisites:"
echo "  1. Redis server running: redis-server"
echo "  2. MongoDB running: mongod"
echo ""

# Check if Redis is running
if ! command -v redis-cli &> /dev/null || ! redis-cli ping &> /dev/null; then
    echo "WARNING: Redis doesn't seem to be running."
    echo "Start it with: brew services start redis (macOS) or redis-server"
    echo ""
fi

# Check if MongoDB is running
if ! command -v mongosh &> /dev/null; then
    echo "WARNING: MongoDB CLI not found."
    echo "Install with: brew install mongodb-community (macOS)"
    echo ""
fi

cd "$(dirname "$0")"

echo "Starting services..."

# Start Django backend
echo "[1/3] Starting Django backend..."
cd backend
source venv/bin/activate
python manage.py runserver 8000 &
DJANGO_PID=$!
cd ..

# Start Celery worker
echo "[2/3] Starting Celery worker..."
cd backend
source venv/bin/activate
celery -A core worker --loglevel=info &
CELERY_PID=$!
cd ..

# Start React frontend
echo "[3/3] Starting React frontend..."
cd frontend
npm start &
REACT_PID=$!
cd ..

echo ""
echo "=== All services started ==="
echo "Django:  http://localhost:8000 (PID: $DJANGO_PID)"
echo "Celery:  worker running (PID: $CELERY_PID)"
echo "React:   http://localhost:3000 (PID: $REACT_PID)"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for any process to exit
wait

# Cleanup
kill $DJANGO_PID $CELERY_PID $REACT_PID 2>/dev/null
