# Multi-stage optimized build for API Gateway (Deno)
# Build stage
FROM denoland/deno:1.39.2-debian as builder

# Set build arguments for metadata
ARG BUILD_DATE=""
ARG VCS_REF=""
ARG VERSION="latest"

# Add OCI metadata
LABEL maintainer="API Team" \
      org.opencontainers.image.title="API Gateway" \
      org.opencontainers.image.description="API Gateway service for routing, load balancing, and authentication" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/company/api-gateway" \
      org.opencontainers.image.licenses="MIT"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy dependency files
COPY deno.json* ./
COPY deps.ts* ./

# Download and cache dependencies
RUN deno cache deps.ts

# Copy application code
COPY . .

# Compile TypeScript
RUN deno cache --unstable main.ts

# Production stage
FROM denoland/deno:1.39.2-debian as production

# Create non-root user and set up permissions
RUN groupadd --gid 1001 deno && \
    useradd --uid 1001 --gid deno --shell /bin/bash --create-home deno && \
    apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy application from builder
COPY --from=builder --chown=deno:deno /app/deps.ts /app/
COPY --from=builder --chown=deno:deno /app/main.ts /app/
COPY --from=builder /deno-dir/ /deno-dir/

# Set ownership for deno directory
RUN chown -R deno:deno /deno-dir

# Switch to non-root user
USER deno

# Health check with proper error handling
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD deno run --allow-net --allow-env --allow-read --allow-write main.ts health || exit 1

# Expose port
EXPOSE 3000

# Set environment variables for optimal performance
ENV DENO_DIR=/deno-dir \
    DENO_NO_UPDATE_CHECK=1 \
    DENO_NO_PACKAGE_JSON=1

# Run application with optimal settings
CMD ["deno", "run", "--allow-net", "--allow-env", "--allow-read", "--allow-write", "--no-prompt", "main.ts"]
