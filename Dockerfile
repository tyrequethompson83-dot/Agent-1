FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN pip install --upgrade pip && pip install .
RUN playwright install --with-deps chromium

RUN useradd -m -u 10001 agent && mkdir -p /app/data && chown -R agent:agent /app

USER agent

CMD ["python", "-m", "agent1.main"]

