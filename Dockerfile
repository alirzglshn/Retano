# syntax=docker/dockerfile:1

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: builder — compiles wheels for anything needing a C toolchain
# (psycopg2, cryptography, pillow, numpy, pandas) so the runtime image never
# needs gcc/build-essential/postgres headers at all.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Wheels go to /build/wheels; installed for real in the runtime stage.
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: runtime — slim, no compilers, only the shared libs actually
# needed at runtime (libpq5 for psycopg, not the full libpq-dev headers).
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Do not buffer stdout/stderr (immediate log visibility) and do not write
# .pyc files into the image layer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 django \
    && useradd --uid 1000 --gid django --shell /bin/bash --create-home django

WORKDIR /app

COPY --from=builder /build/wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY --chown=django:django . .

RUN mkdir -p /app/staticfiles /app/media /var/log/retano \
    && chown -R django:django /app/staticfiles /app/media /var/log/retano

USER django

ENV DJANGO_SETTINGS_MODULE=config.settings.production

# collectstatic here bakes static files into the image itself, so the
# nginx container can mount/share the same volume without a separate
# "run collectstatic in prod" step. Requires DJANGO_SECRET_KEY and the
# DB_* vars to be present at *build* time only because base.py raises
# RuntimeError if they're missing at import time -- dummy build-time
# values are injected via --build-arg in the compose/CI build step so
# this never touches a real database (collectstatic does not connect
# to the DB, it only imports settings).
ARG DJANGO_SECRET_KEY=build-time-placeholder-not-used-at-runtime
ARG DB_NAME=build
ARG DB_USER=build
ARG DB_PASSWORD=build
ARG DB_HOST=build
ARG DB_PORT=5432
ENV DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY} \
    DB_NAME=${DB_NAME} \
    DB_USER=${DB_USER} \
    DB_PASSWORD=${DB_PASSWORD} \
    DB_HOST=${DB_HOST} \
    DB_PORT=${DB_PORT}

RUN python manage.py collectstatic --noinput

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/admin/login/ || exit 1

# Real runtime env vars (DB, Redis, secrets) are injected by docker-compose
# --env-file at container start, overriding the build-time placeholders above.
CMD ["gunicorn", "Retano.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--threads", "2", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
