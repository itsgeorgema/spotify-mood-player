# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the backend requirements file into the container at /app
COPY backend/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory into the container at /app/backend
COPY backend/ ./backend

# Make port 8080 available to the world outside this container
# Fly.io will map its internal port to this one.
EXPOSE 8080

# Define environment variable for the port Gunicorn will listen on
ENV PORT 8080
ENV FLASK_ENV production


# Run app.py when the container launches using Gunicorn
# Gunicorn is a production-ready WSGI HTTP server for UNIX.
# We point it to the 'app' Flask instance within your 'app.py' file.
# The working directory is /app, so backend.app means /app/backend/app.py
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "backend.app:app"]