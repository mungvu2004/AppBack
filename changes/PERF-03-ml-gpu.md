# PERF-03 — perf/ml-gpu (P1): suy luận ONNX chạy GPU khi có

- `apps/ml/runtime/loader.py`: `select_providers(ML_DEVICE)` — `cpu` → CPU; `cuda` → CUDA rồi CPU; `auto` → CUDA chỉ khi `onnxruntime` đang cài có `CUDAExecutionProvider`. Phiên CUDA gọi `ort.preload_dlls()` (bọc an toàn), tạo lỗi → cảnh báo và dựng lại CPU; log `session.get_providers()` mỗi model (một lần nhờ cache LRU).
- `deploy/docker/ml.Dockerfile` (`ML_VARIANT=cuda`): gỡ `onnxruntime` CPU, cài `onnxruntime-gpu==1.29.0` từ feed CUDA 12 chính thức `--no-deps` + gói `nvidia-*-cu12` (cudart, nvrtc, cublas, cufft, curand, cudnn 9). PyPI 1.30.0 là bản CUDA 13, feed CUDA 12 dừng ở 1.29.0 (curl 2026-10-27). Kiểm cuối tầng dựng thêm: ảnh cuda có CUDA EP, không còn `onnxruntime` CPU. Ảnh cpu và `uv.lock` không đổi.
- Còn CPU: bộ dò RapidOCR (`apps/ml/text/reader.py`, nhánh perf/ml-workers sở hữu; `TextDetector` nhận `use_cuda` trong cấu hình `Det`), phiên kiểm xuất ONNX ở huấn luyện.
- Test: `apps/ml/runtime/tests/test_loader_providers.py` (chọn providers, lùi CPU, preload thiếu/lỗi; một test `gpu` cho máy có GPU).
