# PERF-03 — api-workers (P4, P11-BE)

- P4: `api` chạy `uvicorn --workers ${API_WORKERS}` (mặc định 4) ở cả `api.Dockerfile` và `deploy/compose/base.yml`. Đo gốc: `/projects/{id}/spatial` p50 39 ms (1 req) → 965 ms (16 đồng thời), trần ~20 req/s với 1 tiến trình trên 12 CPU.
- Pool DB mỗi worker hạ còn `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=3` (+ pool claim 5): 4 worker = 52 kết nối < 60 trên 100 `max_connections`. Chỉnh qua `API_WORKERS`/`API_DB_POOL_SIZE`/`API_DB_MAX_OVERFLOW`.
- Trần SSE toàn cục `STREAM_MAX_GLOBAL` (semaphore + pool Redis SSE, trong tiến trình) nay chia cho `API_WORKERS` (`StreamSettings.stream_max_per_process`), tổng N worker không vượt 500.
- Đã kiểm, không cần đổi: trần SSE theo người dùng (ZSET Redis), rate-limit (Redis Lua), cache principal (Redis, TTL), khoá đăng nhập (Redis `safe`); `lifespan` không chạy migration (dịch vụ `migrate` riêng).
- Nhân theo N, ghi nhận: executor argon2 `PASSWORD_HASH_CONCURRENCY=4` và semaphore giải mã avatar/ảnh quality là theo tiến trình → 4 worker = tối đa 16 lượt băm song song (cả RAM argon2 ×4); hạ `PASSWORD_HASH_CONCURRENCY` nếu đo thấy nghẽn.
- P11-BE: `member_users` chỉ nạp `id, email, name, role, avatar_key` (`load_only`), bỏ JSONB `preferences`; hình dạng phản hồi/openapi không đổi (`UserSchema` không có `preferences`).
