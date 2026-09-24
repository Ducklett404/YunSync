FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    FORWARDED_ALLOW_IPS=127.0.0.1 \
    UPLOAD_STORAGE_DIR=/app/uploads
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./
COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist
RUN addgroup --system --gid 10001 yunsync \
    && adduser --system --uid 10001 --ingroup yunsync --home /home/yunsync yunsync \
    && mkdir -p /app/backend/data /app/uploads \
    && chown -R yunsync:yunsync /app/backend/data /app/uploads
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/healthz', timeout=2).read()" || exit 1
CMD ["sh", "-c", "exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips ${FORWARDED_ALLOW_IPS} --no-server-header"]
