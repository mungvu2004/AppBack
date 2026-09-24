# Ảnh `worker` (kiêm `beat`, compose đổi lệnh) — B0-08 §1 (hop-dong.md).
# Chép thêm `apps/api/` vì lịch của module API nằm ở `apps/api/*/jobs.py`
# (BE-00 §6); import-linter giữ các module đó không nhập fastapi/starlette/
# uvicorn/jwt/argon2, nên ảnh này không cài các gói đó (BE-00 §2.1).

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS deps
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY packages/domain/pyproject.toml packages/domain/pyproject.toml
COPY packages/vision/pyproject.toml packages/vision/pyproject.toml
COPY packages/db/pyproject.toml packages/db/pyproject.toml
COPY packages/storage/pyproject.toml packages/storage/pyproject.toml
COPY packages/messaging/pyproject.toml packages/messaging/pyproject.toml
COPY packages/mail/pyproject.toml packages/mail/pyproject.toml
COPY packages/observability/pyproject.toml packages/observability/pyproject.toml
COPY packages/ml_contracts/pyproject.toml packages/ml_contracts/pyproject.toml
COPY packages/testing/pyproject.toml packages/testing/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY apps/ml/pyproject.toml apps/ml/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package appback-worker

# Minor PHẢI khớp tầng dựng (uv:python3.12) và `requires-python` của
# pyproject.toml gốc: venv nằm ở /opt/venv/lib/python3.12 với C extension
# cp312, tầng chạy lệch minor thì mọi gói biến mất dù build vẫn thoát 0
# (NO-177, FIX-104). Nâng minor là việc có chủ đích, kèm `run.sh lock`.
FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS runtime
WORKDIR /app
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH

COPY --from=deps /opt/venv /opt/venv

COPY apps/__init__.py apps/__init__.py
COPY apps/worker/ apps/worker/
COPY apps/api/ apps/api/
COPY packages/__init__.py packages/__init__.py
COPY packages/core/ packages/core/
COPY packages/domain/ packages/domain/
COPY packages/vision/ packages/vision/
COPY packages/db/ packages/db/
COPY packages/storage/ packages/storage/
COPY packages/messaging/ packages/messaging/
COPY packages/mail/ packages/mail/
COPY packages/observability/ packages/observability/
COPY packages/ml_contracts/ packages/ml_contracts/

RUN mkdir -p /var/lib/appback/storage \
 && chown -R 10001:10001 /var/lib/appback/storage \
 && chmod -R a+rX /app

USER 10001

HEALTHCHECK --interval=15s --timeout=10s --start-period=10s --retries=3 \
  CMD celery -A apps.worker.celery_main inspect ping -d celery@$HOSTNAME --timeout 5

CMD ["celery", "-A", "apps.worker.celery_main", "worker", "-Q", "default,pipeline.cpu"]
