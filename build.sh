#!/usr/bin/env bash
# Build script for Render - builds both frontend and backend

set -o errexit  # Exit on error

echo "=== Building Frontend ==="
cd frontend
npm install
npm run build
cd ..

echo "=== Setting up Backend ==="
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Create staticfiles directory structure
mkdir -p staticfiles/frontend

# Copy React build to Django staticfiles
echo "=== Copying React build to Django ==="
cp -r ../frontend/build/* staticfiles/frontend/

# Run Django collectstatic
echo "=== Running collectstatic ==="
python manage.py collectstatic --noinput

echo "=== Build Complete ==="
