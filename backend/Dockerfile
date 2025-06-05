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

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable for the port Gunicorn will listen on
ENV PORT 8080
ENV FLASK_ENV production

# Download the VADER lexicon
RUN python -m nltk.downloader vader_lexicon

# Use a longer timeout for both development and production to avoid worker timeouts during analysis
CMD ["gunicorn", "--timeout", "300", "--bind", "0.0.0.0:8080", "app:app"]
# CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"] 