# syntax=docker/dockerfile:1

# Use an official Python runtime as a parent image
ARG PYTHON_VERSION=3.11-slim
FROM python:${PYTHON_VERSION} AS base

# Set environment variables for Python and Flask
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    FLASK_APP="backend.app:app" \
    FLASK_ENV="production"
    # The PORT environment variable will be supplied by Fly.io or default in the CMD

# Install any needed system dependencies here if your Python packages require them
# Example: RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev build-essential && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Create and activate a virtual environment
# This helps keep dependencies isolated
RUN python -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"

# Install Python dependencies
# Copy requirements.txt first to leverage Docker layer caching
# This assumes your requirements.txt is inside the 'backend' folder in your project
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Install Gunicorn, a WSGI HTTP server for Python web applications
RUN pip install gunicorn

# Copy the backend application code into the container
# This assumes your backend code (app.py, spotify_service.py, etc.) is in a 'backend' subdirectory
# in your project root, and it will be copied to /app/backend/ in the image.
COPY backend/ ./backend/

# Inform Docker that the container listens on the specified port at runtime.
# Gunicorn will bind to the port specified by the PORT env var (defaulting to 5001).
EXPOSE 5001

# Command to run the Gunicorn server when the container launches.
# Gunicorn will change to the 'backend' directory and look for an 'app' instance in 'app.py'.
# Workers and threads can be adjusted based on your application's needs and machine resources.
# The PORT environment variable is used by Gunicorn, which Fly.io will set.
CMD ["gunicorn", "--chdir", "backend", "app:app", "-w", "2", "--threads", "4", "-b", "0.0.0.0:${PORT:-5001}"]
