# Build stage
FROM python:3.11-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir build hatchling

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN python -m build --wheel

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/karabo_ml-*.whl && rm /tmp/karabo_ml-*.whl

# Create non-root user
RUN addgroup --system kb && adduser --system --ingroup kb kbuser
USER kbuser

ENTRYPOINT ["kb"]
CMD ["--help"]
