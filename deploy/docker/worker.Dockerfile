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
COPY packages/genai/pyproject.toml packages/genai/pyproject.toml
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
FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS runtime
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
COPY packages/genai/ packages/genai/

RUN mkdir -p /var/lib/appback/storage \
 && chown -R 10001:10001 /var/lib/appback/storage \
 && chmod -R a+rX /app

USER 10001

# Mỗi lượt ping dựng cả một tiến trình Celery (~1 nhân CPU): 30 s thay 15 s (PERF-03 P20).
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD celery -A apps.worker.celery_main inspect ping -d celery@$HOSTNAME --timeout 5

CMD ["celery", "-A", "apps.worker.celery_main", "worker", "-Q", "default,pipeline.cpu"]

# Ảnh `bake` (LB-01): worker + Blender 4.5 LTS chạy nền (`-b`) cho hàng `bake`.
# Dựng riêng bằng `--target bake`; không có `--target` thì tầng cuối (`worker`) thắng
# và BuildKit bỏ qua tầng này. Thư viện X/GL: Blender nạp động kể cả khi chạy nền.
# SHA-256 lấy từ blender-4.5.15.sha256 trên download.blender.org (2026-11-01).
# Tải ở tầng riêng không phụ thuộc mã: sửa mã chỉ dựng lại tầng `bake`, không tải lại ~300 MB.
FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS blender
ARG BLENDER_VERSION=4.5.15
ARG BLENDER_SHA256=0d2b8bb2efe97e6c8eb57de6b7322f8800e1984e3125b60decca5f6771e4773e
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
 && curl -fsSL -o /tmp/blender.tar.xz \
      "https://download.blender.org/release/Blender4.5/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
 && echo "${BLENDER_SHA256}  /tmp/blender.tar.xz" | sha256sum -c - \
 && mkdir -p /opt/blender \
 && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 \
 && rm /tmp/blender.tar.xz

FROM runtime AS bake
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libxi6 libxkbcommon0 libsm6 libxrender1 libgl1 libxxf86vm1 libxfixes3 libegl1 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=blender /opt/blender /opt/blender
RUN /opt/blender/blender --version
ENV BLENDER_BIN=/opt/blender/blender \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
    NVIDIA_VISIBLE_DEVICES=all
USER 10001
CMD ["celery", "-A", "apps.worker.celery_main", "worker", "-Q", "bake", "--concurrency", "1"]

# Tầng cuối = mục tiêu mặc định: ảnh worker thường (không Blender).
FROM runtime AS worker
USER 10001
