# ==============================================================================
# Stage 1: Builder Stage
# Compiles wheels and builds virtual environment with all production dependencies
# ==============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies for C extensions / compiled packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create isolated Python virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install production dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Stage 2: Test Target Stage (Used by docker-compose.test.yml)
# Isolated test execution stage with pytest and testing utilities
# ==============================================================================
FROM builder AS test

WORKDIR /app

# Install test dependencies into virtual environment
RUN /opt/venv/bin/pip install --no-cache-dir pytest>=8.2.0 pytest-asyncio>=0.23.0

# Copy all application code, migrations, artifacts, and test suites
COPY pyproject.toml .
COPY alembic.ini .
COPY alembic ./alembic
COPY artifacts ./artifacts
COPY app ./app
COPY tests ./tests

CMD ["pytest", "-v"]

# ==============================================================================
# Stage 3: Slim Production Runtime Stage (Default final image)
# Minimal, secure production image running Uvicorn as non-root user
# ==============================================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime utilities (curl for container healthcheck, libgomp1 for XGBoost OpenMP)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user and group
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser

# Copy prepared virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Configure environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy database migration files, ML pipeline artifacts, and application source
COPY alembic.ini .
COPY alembic ./alembic
COPY artifacts ./artifacts
COPY app ./app

# Set non-root permissions across application directory
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose standard API port
EXPOSE 8000

# Start Uvicorn ASGI server with automatic migrations and dynamic cloud port support
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
