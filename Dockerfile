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

# Copy the current directory contents into the container at /app
COPY . /app

# =============================================================================
# SECURITY: Set proper ownership and permissions
# =============================================================================
RUN chown -R appuser:appgroup /app && \
    mkdir -p /app/backend/sessions /app/backend/logs /app/backend/chroma_db && \
    chown -R appuser:appgroup /app/backend/sessions /app/backend/logs /app/backend/chroma_db

RUN chmod 700 /app/backend/sessions /app/backend/logs

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

# =============================================================================
# SECURITY: Run as non-root user
# =============================================================================
USER appuser

# Health check
HEALTHCHECK --interval=2m --timeout=10s --start-period=2m --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# Run with gunicorn for production serving
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --timeout 120 --access-logfile - app:app"]

