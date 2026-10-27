# PERF-03 — cổng verify nhanh hơn (phần A: hạ tầng)

- venv cổng dùng chung theo băm `uv.lock` + phiên bản uv (`/work/venv-lock-<băm>`), `flock` quanh `uv sync`;
  worktree mới không cài lại cả venv (đo: 473 s → 196 s khởi động `shell`, `uv sync` chỉ còn biên dịch .pyc).
- `gc` giữ 3 venv theo băm mới nhất (như cache mypy theo băm).
- `test_durations.json` sinh lại từ junit cổng 2026-10-26 (503 tệp, bảng cũ thiếu/lệch).
