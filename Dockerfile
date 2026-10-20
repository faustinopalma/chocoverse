FROM python:3.13.13-slim-trixie@sha256:aa938a849bcb82dce8f49480f056ab82bf5c1c3ebc294f0430f37b6820e7f286
ARG PACKAGE_REFRESH=manual
RUN echo "Security package refresh: $PACKAGE_REFRESH" \
    && apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY config ./config
RUN python -m pip install --no-cache-dir --upgrade pip==26.2.1 \
    && python -m pip install --no-cache-dir '.[runtime]'
USER 65532:65532
ENV PYTHONUNBUFFERED=1 GIANDORIA_ROOT=/app
RUN python -m pip check \
    && python -c "import ssl, sqlite3, azure.identity, azure.eventhub, requests, websocket, giandoria.runtime"
ENTRYPOINT ["python", "-m", "giandoria.runtime"]
