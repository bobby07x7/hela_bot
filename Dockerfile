FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Default command runs the bot; the dashboard API can be run from the same
# image with `docker compose run bot python -m dashboard.api.main` or via
# the separate `api` service in docker-compose.yml.
CMD ["python", "main.py"]
