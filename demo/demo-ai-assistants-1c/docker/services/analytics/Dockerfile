# Multi-stage optimized build for Analytics Service
# Build stage
FROM python:3.11-slim as builder

# Set build arguments for metadata
ARG BUILD_DATE=""
ARG VCS_REF=""
ARG VERSION="latest"

# Add OCI metadata
LABEL maintainer="Analytics Team" \
      org.opencontainers.image.title="Analytics Service" \
      org.opencontainers.image.description="Data analytics and reporting microservice with FastAPI" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/company/analytics-service" \
      org.opencontainers.image.licenses="MIT"

# Install build dependencies in a single layer
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /build

# Copy and install Python dependencies with pip cache optimization
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --compile --prefix=/install -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Install runtime dependencies and create non-root user
RUN groupadd --gid 1001 app && \
    useradd --uid 1001 --gid app --shell /bin/bash --create-home app && \
    apt-get update && apt-get install -y \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=app:app . .

# Switch to non-root user
USER app:app

# Health check with proper error handling
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

# Expose port
EXPOSE 8003

# Set Python optimizations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Run application with optimal settings
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "2", "--access-log"]
