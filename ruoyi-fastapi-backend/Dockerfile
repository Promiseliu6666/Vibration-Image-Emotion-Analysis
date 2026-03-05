FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Working directory
WORKDIR /app

# Install system dependencies needed by common Python packages (e.g., opencv, cryptography)
RUN sed -i 's#http://deb.debian.org/debian#http://mirrors.xjtu.edu.cn/debian#g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . /app

RUN uv lock && uv sync --locked

# Runtime environment: load prod config by default
ENV APP_ENV=prod

# Expose application port
EXPOSE 9099

# Healthcheck (checks FastAPI OpenAPI endpoint under root path)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:9099/prod-api/openapi.json || exit 1

# Start the application (ensure prod env is used)
CMD ["uv", "run", "app.py", "--env", "prod"]