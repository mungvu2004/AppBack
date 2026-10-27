# Ảnh `ml` — B0-08 §1 (hop-dong.md). `ML_VARIANT=cuda` là ngoại lệ DUY NHẤT
# ngoài `uv.lock`: thay torch/torchvision CPU đã khoá bằng bản CUDA cùng
# phiên bản, tải thẳng từ chỉ mục PyTorch chính thức (không qua uv lock).
#
# Bằng chứng tên wheel cho CUDA_TAG=cu126 (người điều phối `curl` chỉ mục
# https://download.pytorch.org/whl/cu126/, 2026-09-22 — hop-dong.md §1;
# torch 2.14.0/torchvision 0.29.0 KHÔNG có ở cu118/cu121/cu124/cu128/cu129):
#   torch-2.14.0+cu126-cp312-cp312-manylinux_2_28_x86_64.whl
#   torchvision-0.29.0+cu126-cp312-cp312-manylinux_2_28_x86_64.whl
#
# Suy luận GPU (PERF-03 P1): biến thể cuda gỡ `onnxruntime` CPU 1.30.0 (của
# uv.lock), cài `onnxruntime-gpu` bản CUDA 12 + cuDNN 9, `--no-deps` để
# rapidocr không kéo lại bản CPU. Bằng chứng (`curl`, 2026-10-27):
#   PyPI onnxruntime-gpu 1.30.0 là bản CUDA 13 (extras nvidia-cuda-runtime
#   ~=13.0, nvidia-cudnn-cu13) — KHÔNG khớp CUDA 12.6 của torch cu126;
#   feed CUDA 12 chính thức (ORT_CUDA12_INDEX) mới nhất là 1.29.0:
#   onnxruntime_gpu-1.29.0-cp312-cp312-manylinux_2_28_x86_64.whl
# nên dùng 1.29.0 (lệch một minor với bản CPU, chỉ ở ảnh cuda). Torch cài
# `--no-deps` nên ảnh chưa có gói nvidia-*-cu12 (trước PERF-03 `import torch`
# của ảnh cuda hỏng: "libcublasLt.so.*[0-9] not found"): cài đúng các gói
# nvidia-* + cuda-toolkit[...]/cuda-bindings mà metadata torch cu126 khai (CUDA
# EP của ORT cần); loader gọi `onnxruntime.preload_dlls()` để nạp chúng.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS deps
ARG ML_VARIANT=cpu
ARG CUDA_TAG=cu126
ARG ORT_GPU_VERSION=1.29.0
ARG ORT_CUDA12_INDEX=https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/
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
        "torch==2.14.0+${CUDA_TAG}" "torchvision==0.29.0+${CUDA_TAG}" \
   && uv pip uninstall --python /opt/venv/bin/python onnxruntime \
   && uv pip install --python /opt/venv/bin/python --no-deps \
        --index-url "${ORT_CUDA12_INDEX}" "onnxruntime-gpu==${ORT_GPU_VERSION}" \
   && /opt/venv/bin/python -c "import importlib.metadata as m; print('\n'.join(r.split(';')[0].strip() for r in m.requires('torch') or [] if r.startswith(('nvidia-', 'cuda-')) and 'extra ==' not in r))" > /tmp/torch-cuda-deps.txt \
   && uv pip install --python /opt/venv/bin/python -r /tmp/torch-cuda-deps.txt; \
    fi

# CUDA EP của onnxruntime-gpu 1.29 dựng trên CUDA 12.8+: với libcudart 12.6 của cuda-toolkit
# (torch cu126) nó hỏng "undefined symbol: cudaLibraryGetKernel" rồi rơi về CPU (đo 27/10).
# cudart 12.9 cùng mức cuBLAS 12.9 đã có; torch cu126 chạy được trên cudart mới hơn cùng dòng 12.
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$ML_VARIANT" = "cuda" ]; then \
      uv pip install --python /opt/venv/bin/python "nvidia-cuda-runtime-cu12>=12.9,<13"; \
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
COPY packages/observability/ packages/observability/
COPY packages/ml_contracts/ packages/ml_contracts/

# Trọng số nhà cung cấp ghim SHA-256, xuất ONNX — có mạng lúc build (BE-00 §9).
# Hỏng ở đây → build `ml` hỏng thật (không bỏ bước, hợp đồng §5).
RUN python -m packages.ml_contracts.pinned fetch --dest /opt/models \
 && python -m apps.ml.runtime.export_pinned --dest /opt/models

# Kiểm cuối tầng dựng: đủ mọi thư viện suy luận, không có `opencv-python`/
# `opencv-contrib-python` bản GUI (K29, review 2026-09-22 #13; venv của uv
# không có `pip` nên dùng `importlib.metadata`). Ảnh cuda: ORT có CUDA EP
# (danh sách lúc biên dịch, build không cần GPU) và không còn bản CPU.
RUN python -c "\
import importlib.metadata as m, os; \
import cv2, onnxruntime, torch, torchvision, rapidocr_onnxruntime; \
torchvision.ops.nms; \
names = {d.metadata['Name'] for d in m.distributions()}; \
assert 'opencv-python' not in names, names; \
assert 'opencv-contrib-python' not in names, names; \
cuda = os.environ['ML_VARIANT'] == 'cuda'; \
assert not cuda or 'CUDAExecutionProvider' in onnxruntime.get_available_providers(), onnxruntime.get_available_providers(); \
assert not cuda or 'onnxruntime' not in names, names"

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
COPY --from=deps /opt/models /opt/models
COPY --from=deps /app/apps/__init__.py apps/__init__.py
COPY --from=deps /app/apps/ml/ apps/ml/
COPY --from=deps /app/packages/__init__.py packages/__init__.py
COPY --from=deps /app/packages/core/ packages/core/
COPY --from=deps /app/packages/domain/ packages/domain/
COPY --from=deps /app/packages/vision/ packages/vision/
COPY --from=deps /app/packages/storage/ packages/storage/
COPY --from=deps /app/packages/messaging/ packages/messaging/
COPY --from=deps /app/packages/observability/ packages/observability/
COPY --from=deps /app/packages/ml_contracts/ packages/ml_contracts/

# `/opt/models` chỉ đọc với 10001 (hợp đồng §1).
RUN chmod -R a+rX /app \
 && chmod -R 555 /opt/models

USER 10001

CMD ["celery", "-A", "apps.ml.celery_main", "worker", "-Q", "ml.infer,ml.training", "--concurrency", "1"]
