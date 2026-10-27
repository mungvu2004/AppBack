# PERF-03 — cổng nhanh mỗi lần sửa, cổng đầy đủ khởi động nhanh hơn

- `run.sh verify --fast`: ruff, lint-imports, mypy nền trên cache ấm `mypy-fast-<worktree>`, pytest **chỉ đơn vị bị chạm**
  so với `main` (đổi `conftest.py`/`pyproject.toml`/`uv.lock`/`packages/testing/fixtures/` thì cả bộ), không độ phủ, không
  5b/7/8; bước 6 khi migration đổi. Đo ấm: 35 s trong container (`apps/api/auth`) + ~15 s khởi động. Xem trước, `verify`
  đầy đủ trước merge vẫn là phán quyết.
- Khởi động cổng 144 s → 15 s: venv dùng chung theo băm `uv.lock` + phiên bản uv (`/work/venv-lock-*`, `flock`; worktree
  mới không cài lại venv, 473 s), bỏ `compose build` khi nhãn ảnh trùng băm Dockerfile, bỏ `uv sync` khi lock + pyproject
  + uv không đổi. `gc` giữ 3 venv theo băm mới nhất.
- Bước 5 giữ `-n 6 --dist loadfile`: `-n 10` bị OOM trong VM 12 GB; `loadgroup` + nhóm theo tệp không được áp (test cùng
  tệp xé ra mọi worker, pytest 585 → 1.108 s) nên bỏ. Plugin `worker_rss` in RSS đỉnh mỗi worker (đo: 1,7–2,6 GiB).
- `test_durations.json` sinh lại từ junit 2026-10-26; import nặng trong vài test ML và `ml_ocr` dời vào hàm (không giảm RSS: worker vẫn collect cả bộ; đo 1,7–2,6 GiB/worker).
- Không endpoint, không bảng, không migration, không đổi dây: bước 6, 7, 8 không có gì mới để kiểm.
