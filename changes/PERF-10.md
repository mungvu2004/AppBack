# PERF-10 — cổng test dùng Postgres/Redis/MinIO của stack f14 đang chạy

- `run.sh`: stack `VERIFY_SHARED_STACK` (mặc định `f14`, `off` tắt) có đủ postgres, redis-broker, redis-cache, minio đang
  chạy → đặt `TEST_SHARED_*` (IP trên `<stack>_appback`, mật khẩu đọc từ env container lúc chạy) qua `verify.yml`;
  fixture `services.py` dùng thẳng dịch vụ đó, bớt 4 container mỗi lượt. Không có stack → y như trước, CI không đổi.
- Rào: Postgres chỉ nối `postgres` + `assert_test_database` chặn `CREATE`/`DROP` tên không phải test; Redis khối DB sau
  khối app, kiểm `maxmemory-policy` + `databases` (sai → container, có cảnh báo), `FLUSHDB` khối mình trước khi dùng;
  MinIO chỉ bucket ngẫu nhiên, `s3_storage` xoá bucket của mình khi dùng chung. Mailpit, `ephemeral_*` vẫn container.
- `in_container.sh`: `flock /work/shared-stack.lock` — một lượt một lúc trên stack, lượt khác về container riêng.
- `deploy/compose/base.yml`: Redis `--databases 128` (đủ khối cho 6 tiến trình xdist × 5 mã); stack cần tạo lại Redis.
- Không endpoint, không bảng, không migration, không đổi dây: bước 6, 7, 8 không có gì mới để kiểm.
