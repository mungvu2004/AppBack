# PERF-04 — cổng nhanh chọn test theo đồ thị import, đo độ phủ đơn vị bị chạm

- `run.sh verify --fast`: pytest chỉ các tệp test bị ảnh hưởng (`tools/verify/affected.py`): test của đơn vị bị chạm, test
  nhập bắc cầu module đổi (grimp, đồ thị của lint-imports), test xin fixture mà module fixture nhập module đổi. Cả bộ khi đổi
  `conftest.py`, `pyproject.toml`, `uv.lock`, `packages/testing/`, migration hay đầu vào bước 7 (mẫu golden phải đủ).
- Bước 5 nhanh đo độ phủ + `coverage_gate` trên đơn vị bị chạm; bước 6/7/8 chạy khi đầu vào của chúng đổi
  (`FAST_STEP_INPUTS`). Cổng đầy đủ không đổi.
- `test_main_ignores_override_outside_test_env` kiểm trong tiến trình thay `python -m` (tiến trình con nạp mọi trainer,
  quá trần 110 s khi máy tải).
- `run.sh`: cache AppFront theo SHA dùng chung mọi worktree (`<.git chung>/verify-appfront`) — worktree mới không giải
  nén lại (~40 s); cổng nhanh in `--durations=10`.
- Không endpoint, không bảng, không migration, không đổi dây: bước 6, 7, 8 không có gì mới để kiểm.
