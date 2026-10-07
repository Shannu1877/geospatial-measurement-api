# ==============================================================================
# Multi-Stage Production Dockerfile for Geospatial Measurement API
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build stage (compile/install dependencies)
# ------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install virtual environment and python packages
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Runtime stage (minimal image with non-root user)
# ------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runner

WORKDIR /app

# Install minimal runtime system utilities (e.g. curl for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and group
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UPLOAD_DIR=/app/uploads \
    DATABASE_URL=sqlite:////app/data/geospatial.db

# Create directories for data and uploads with proper permissions
RUN mkdir -p /app/uploads /app/data && \
    chown -R appuser:appgroup /app

# Copy application source code
COPY --chown=appuser:appgroup app/ /app/app/
COPY --chown=appuser:appgroup pyproject.toml /app/

# Switch to non-root user
USER appuser

# Health check against /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Start Uvicorn ASGI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
