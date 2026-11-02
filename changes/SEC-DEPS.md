# SEC-DEPS — vá lỗ hổng thư viện và ảnh nền do CI báo (02/11/2026)

- pip-audit (job `lint`): sàn `constraint-dependencies` ở `[tool.uv]` gốc, `run.sh lock` nâng certifi 2026.10.23,
  filelock 4.2.6, mako 1.4.3, pillow 13.0.0, setuptools 84.2.1, werkzeug 3.1.9; không gói nào khác đổi.
- trivy (job `build`): tầng chạy api/worker/ml lên `python:3.12-slim-bookworm@sha256:e697c818…` (28/10, Debian 12.15,
  perl-base 5.36.0-7+deb12u4); trivy 0.74.0 CRITICAL `--ignore-unfixed` trên ảnh nền: 0.
- Không đổi API, DB, migration, hợp đồng FE–BE. Cổng áp dụng: cả bộ test (uv.lock đổi), dựng ảnh ở CI.
