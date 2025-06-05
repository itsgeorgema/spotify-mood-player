# Gunicorn configuration file
import multiprocessing

max_requests = 1000
max_requests_jitter = 50

log_file = "-"

# Increase timeout to 10 minutes (600 seconds)
timeout = 600
keepalive = 5

# Worker configuration for parallel processing
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"  # Use gevent for async workers
worker_connections = 2000  # Increased for better parallel processing
threads = 4  # Enable threading per worker

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "spotify-mood-player"

# SSL (if needed)
# keyfile = "path/to/keyfile"
# certfile = "path/to/certfile"