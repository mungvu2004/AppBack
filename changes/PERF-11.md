# PERF-11 — khoá cổng xếp hàng chung cho full, fast, shell và lệnh host

- Đo 01/11 (log 3 ngày, 457 lượt làm việc): 51 lượt quá 60 phút; lúc đo 4 phiên cùng "chờ cổng của phiên khác". Nguyên
  nhân: mỗi phiên tự thăm dò `docker ps | grep verify` (đếm cả `shell`/`--fast`, không thứ tự), script dựng web còn đòi
  RAM trống ≥ 5 GB nên chờ tới hết hạn.
- `tools/verify/gate_lock.sh`: khoá đọc/ghi trên `/work/gate-full.lock` + cửa quay `/work/gate-turn.lock`. Cổng đầy đủ
  và `--steps` giữ một mình; `--fast`, `shell` giữ dùng chung; lượt một mình đang chờ chặn lượt nhẹ mới đến.
- `run.sh hold -- <lệnh>`: container nhỏ giữ khoá một mình trong lúc chạy lệnh host (dựng ảnh web f14).
- Thử trên volume nháp: s giữ → x chờ 6 s → s đến sau x chờ 9 s (không chen); hai s cùng lúc 0 s; `hold` chặn s đúng
  5 s, trả mã thoát của lệnh.
- `run.sh`: gốc so sánh của `--fast` lấy tổ tiên chung gần nhất với `main` hoặc `origin/main`. `main` local chậm 30
  commit làm nhánh tách từ origin/main thấy 47 tệp đổi thay vì 7, `--fast` chạy quá nửa bộ test (> 10 phút).
- Không endpoint, không bảng, không migration, không đổi dây: bước 6, 7, 8 không có gì mới để kiểm.
