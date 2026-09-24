# Ảnh `ml` — B0-08 §1 (hop-dong.md). `ML_VARIANT=cuda` là ngoại lệ DUY NHẤT
# ngoài `uv.lock`: thay torch/torchvision CPU đã khoá bằng bản CUDA cùng
# phiên bản, tải thẳng từ chỉ mục PyTorch chính thức (không qua uv lock).
#
# Bằng chứng tên wheel cho CUDA_TAG=cu126 (người điều phối `curl` chỉ mục
# https://download.pytorch.org/whl/cu126/, 2026-09-22 — hop-dong.md §1;
# torch 2.14.0/torchvision 0.29.0 KHÔNG có ở cu118/cu121/cu124/cu128/cu129):
#   torch-2.14.0+cu126-cp312-cp312-manylinux_2_28_x86_64.whl
#   torchvision-0.29.0+cu126-cp312-cp312-manylinux_2_28_x86_64.whl

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS deps
ARG ML_VARIANT=cpu
ARG CUDA_TAG=cu126
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH=/opt/venv/bin:$PATH

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
    uv sync --locked --no-dev --package appback-ml

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$ML_VARIANT" = "cuda" ]; then \
      uv pip install --python /opt/venv/bin/python --reinstall --no-deps \
        --index-url "https://download.pytorch.org/whl/${CUDA_TAG}" \
        "torch==2.14.0+${CUDA_TAG}" "torchvision==0.29.0+${CUDA_TAG}"; \
    fi

# Mã cần cho `apps.ml`, cộng bản ghim nhà cung cấp (B5-01). `.dockerignore`
# loại `packages/testing` khỏi các COPY thư mục dưới đây.
COPY apps/__init__.py apps/__init__.py
COPY apps/ml/ apps/ml/
COPY packages/__init__.py packages/__init__.py
COPY packages/core/ packages/core/
COPY packages/domain/ packages/domain/
COPY packages/vision/ packages/vision/
COPY packages/storage/ packages/storage/
COPY packages/messaging/ packages/messaging/
COPY packages/ml_contracts/ packages/ml_contracts/

# Trọng số nhà cung cấp ghim SHA-256, xuất ONNX — có mạng lúc build (BE-00 §9).
# Hỏng ở đây → build `ml` hỏng thật (không bỏ bước, hợp đồng §5).
RUN python -m packages.ml_contracts.pinned fetch --dest /opt/models \
 && python -m apps.ml.runtime.export_pinned --dest /opt/models

# Kiểm cuối tầng dựng: đủ mọi thư viện suy luận, không có `opencv-python`/
# `opencv-contrib-python` bản GUI (K29, review 2026-09-22 #13; venv của uv
# không có `pip` nên dùng `importlib.metadata`).
RUN python -c "\
import importlib.metadata as m; \
import cv2, onnxruntime, torch, torchvision, rapidocr_onnxruntime; \
torchvision.ops.nms; \
names = {d.metadata['Name'] for d in m.distributions()}; \
assert 'opencv-python' not in names, names; \
assert 'opencv-contrib-python' not in names, names"

# Minor PHẢI khớp tầng dựng (uv:python3.12) và `requires-python` của
# pyproject.toml gốc: venv nằm ở /opt/venv/lib/python3.12 với C extension
# cp312, tầng chạy lệch minor thì mọi gói biến mất dù build vẫn thoát 0
# (NO-177, FIX-104). Nâng minor là việc có chủ đích, kèm `run.sh lock`.
FROM python:3.14-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS runtime
WORKDIR /app
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH

COPY --from=deps /opt/venv /opt/venv
COPY --from=deps /opt/models /opt/models
COPY --from=deps /app/apps/__init__.py apps/__init__.py
COPY --from=deps /app/apps/ml/ apps/ml/
COPY --from=deps /app/packages/__init__.py packages/__init__.py
COPY --from=deps /app/packages/core/ packages/core/
COPY --from=deps /app/packages/domain/ packages/domain/
COPY --from=deps /app/packages/vision/ packages/vision/
COPY --from=deps /app/packages/storage/ packages/storage/
COPY --from=deps /app/packages/messaging/ packages/messaging/
COPY --from=deps /app/packages/ml_contracts/ packages/ml_contracts/

# `/opt/models` chỉ đọc với 10001 (hợp đồng §1).
RUN chmod -R a+rX /app \
 && chmod -R 555 /opt/models

USER 10001

CMD ["celery", "-A", "apps.ml.celery_main", "worker", "-Q", "ml.infer,ml.training", "--concurrency", "1"]
