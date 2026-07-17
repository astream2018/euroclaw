FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY euroclaw ./euroclaw

RUN pip install --no-cache-dir .

# Run as a non-root user (defense in depth).
RUN useradd --create-home --uid 10001 euroclaw
USER euroclaw

EXPOSE 8000

# OpenTelemetry is ON by default; it degrades gracefully without a collector.
# The default sandbox backend is 'subprocess'. For hardware isolation, deploy on
# a KVM-enabled host and set SANDBOX_BACKEND=firecracker.
CMD ["python", "-m", "euroclaw"]
