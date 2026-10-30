# syntax=docker/dockerfile:1

# ---- Stage 1: build the React frontend ----
FROM node:22-alpine AS web-build
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python deps (shared by dev and prod) ----
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt .
# The base image's bundled pip has known CVEs; upgrade it before installing anything.
RUN pip install --no-cache-dir --upgrade pip==26.2.2 \
 && pip install --no-cache-dir -r requirements.txt

# ---- Dev: code is bind-mounted by docker compose, uvicorn hot-reloads; includes test tools ----
FROM base AS dev
COPY backend/requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---- Prod: what Render runs (web service and cron job use this same image) ----
FROM base AS prod
COPY backend/app ./app
COPY --from=web-build /web/dist ./static
# Never run as root: if the app is ever compromised, the attacker gets an unprivileged user.
RUN useradd --system --uid 10001 ghost
USER ghost
# --proxy-headers: trust Render's proxy for the real client IP (used by rate limiting).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
