# PERF-01 — tốc độ bộ test (không đổi phép kiểm)

- Chỉ đổi mã test, fixture test, công cụ cổng: `packages/testing/**`, `apps/**/tests/**`, `tools/verify/*`,
  `tools/tests/**`, `.github/workflows/ci.yml`; không đổi mã sản phẩm (ngoại lệ: `apps/ml/training_segformer/model.py`
  nạp `transformers` muộn — hành vi giữ nguyên).
- `api_env` dùng hồ sơ argon2 `test`; dọn DB tìm chuỗi qua `pg_depend`; tệp test nặng chạy trước dưới xdist.
- Cổng: nguồn gửi vào container bằng tar, `UV_COMPILE_BYTECODE=1`, cache mypy theo băm cây nguồn, mypy song song bước 5.
- Không endpoint, không bảng, không migration mới: bước 6 (migration) và bước 7 (contract) chạy như thường, không có gì mới để kiểm.
- Số test không giảm (8.411 → ≥ 8.426), ngưỡng độ phủ giữ nguyên.
