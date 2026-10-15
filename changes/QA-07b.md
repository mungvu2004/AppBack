# QA-07b — catalog id cho pytest của `apps/api/me` + PY-NEW B07-G-112

- Chỉ test: thêm dòng `Catalog: <id>.` vào docstring `apps/api/me/tests/*.py` (65 id của catalog QA-07b C4), không đổi logic.
- Test mới `test_me_change_password_hash_executor_busy_is_503` (B07-G-112): bộ băm bận quá `HASH_WAIT_S` → 503 `DEPENDENCY_UNAVAILABLE` + `Retry-After: 1` trên `POST /api/me/password` (trước chỉ đăng nhập có test này).
- Không đổi mã ứng dụng, không đổi dây: bước 6, 7, 8 không có gì mới.
