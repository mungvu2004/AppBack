# Ảnh `api` — B0-08 §1 (hop-dong.md), BE-00 §13.1. Build context = gốc repo.
# Tầng dựng: uv sync workspace ảo (package = false) — mọi thành viên chỉ cần
# pyproject.toml, không cần mã nguồn (ghi-chu-be.md §8). Tầng chạy: không root,
# không `packages/testing`, không `apps/ml`, không `apps/worker`.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS deps
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# uv.lock khoá cả workspace; xoá hẳn một thành viên (kể cả chỉ thiếu
# pyproject.toml) làm `--locked` hỏng (ghi-chu-be.md §8, test 2). Mọi thành
# viên đều `package = false` nên không cần mã nguồn để sync, chỉ cần khai báo.
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
    uv sync --locked --no-dev --package appback-api

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

# Không `COPY . .`: chỉ mã ảnh `api` cần (hợp đồng §1). `.dockerignore` loại
# `packages/testing` khỏi mọi COPY thư mục dưới đây.
COPY apps/__init__.py apps/__init__.py
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

# Đích volume `local-storage` khi STORAGE_BACKEND=local (hợp đồng §1); app
# không tự tạo thư mục.
RUN mkdir -p /var/lib/appback/storage \
 && chown -R 10001:10001 /var/lib/appback/storage \
 && chmod -R a+rX /app

EXPOSE 8000
USER 10001

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]

CMD ["sh", "-c", "exec uvicorn apps.api.core.app:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=${FORWARDED_ALLOW_IPS} --no-access-log"]
