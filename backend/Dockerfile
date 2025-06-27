# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the backend requirements file into the container at /app
COPY requirements.txt .

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory into the container at /app
COPY . .

# Make port 5000 available for local development and 8080 for production
EXPOSE 5000 8080

# Define environment variable for the port
ENV PORT 5000
ENV FLASK_ENV development

# For local development with docker-compose
CMD ["flask", "run", "--host=0.0.0.0"]

# For production: 
# CMD ["gunicorn", "--timeout", "300", "--bind", "0.0.0.0:8080", "app:app"] 