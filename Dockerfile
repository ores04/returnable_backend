FROM python:3.13-slim

# Set environment variables early
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8

WORKDIR /app

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install dependencies first (better layer caching)
COPY ./server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser ./server /app/server

# Switch to non-root user
USER appuser

# Expose FastAPI's default port
EXPOSE 8000

# Fixed CMD - use the correct module path and FastAPI's default port
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]