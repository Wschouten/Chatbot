# Use an official Python runtime as a parent image
# Using Python 3.11 to ensure compatibility with ChromaDB/RAG libraries
FROM python:3.11-slim

# =============================================================================
# SECURITY: Create non-root user
# =============================================================================
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY backend/requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install gosu for privilege dropping at container startup
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*

# Copy the current directory contents into the container at /app
COPY . /app

# =============================================================================
# SECURITY: Set proper ownership and permissions
# =============================================================================
RUN chown -R appuser:appgroup /app && \
    mkdir -p /app/backend/data/sessions /app/backend/data/logs /app/backend/data/chroma_db && \
    chown -R appuser:appgroup /app/backend/data

RUN chmod 700 /app/backend/data/sessions /app/backend/data/logs

# Set environment variable for Flask
ENV FLASK_APP=backend/app.py
ENV FLASK_RUN_HOST=0.0.0.0
# Disable Python bytecode generation (smaller image, no .pyc files)
ENV PYTHONDONTWRITEBYTECODE=1
# Unbuffered output for proper logging
ENV PYTHONUNBUFFERED=1

# Expose port 5000 for the app
EXPOSE 5000

# Run commands from the backend directory context
WORKDIR /app/backend

# Health check
HEALTHCHECK --interval=2m --timeout=10s --start-period=2m --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"5000\")}/health')" || exit 1

# =============================================================================
# SECURITY: Start as root to fix volume permissions, then drop to appuser
# Railway mounts volumes as root-owned, so we must chown at runtime before
# switching to the non-root appuser via gosu.
# =============================================================================
CMD ["sh", "-c", "mkdir -p /app/backend/data/sessions /app/backend/data/logs /app/backend/data/chroma_db && chown -R appuser:appgroup /app/backend/data && exec gosu appuser gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --timeout 120 --access-logfile - app:app"]

