# Use Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install Chromium and dependencies (more reliable than google-chrome in containers)
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    curl \
    unzip \
    xvfb \
    libxi6 \
    libnss3 \
    libxss1 \
    libasound2t64 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libdrm2 \
    libgbm1 \
    fonts-liberation \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    # Install Node.js
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files first for caching
COPY frontend/package*.json ./frontend/

# Install Node dependencies
WORKDIR /app/frontend
RUN npm install

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# Go back to app root
WORKDIR /app

# Copy backend requirements and install
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Setup staticfiles directory and copy React build
RUN mkdir -p backend/staticfiles/frontend \
    && cp -r frontend/build/* backend/staticfiles/frontend/

# Collect static files
WORKDIR /app/backend
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 10000

# Set environment for headless Chromium
ENV SELENIUM_HEADLESS=True
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Start command
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "core.wsgi:application"]
