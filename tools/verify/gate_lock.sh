# Khoá cổng dùng chung cả máy (PERF-11) — `source` từ in_container.sh và từ container giữ khoá của `run.sh hold`.
# Khoá đọc/ghi trên volume `/work` (mọi worktree dùng chung):
#   x = một mình: `verify` đầy đủ / `--steps` (~8,4 GiB), `hold` (dựng ảnh web…);
#   s = dùng chung: `verify --fast`, `shell` — nhiều lượt nhẹ chạy cùng nhau, không lượt nào chạy cạnh lượt x
#       (fast cạnh cổng đầy đủ từng làm sập WSL + Docker, 2026-11-01).
# Cửa quay `gate-turn.lock`: lượt x đang chờ giữ cửa, lượt s mới đến phải chờ sau nó, nên luồng lượt nhẹ không
# chen mãi trước cổng đầy đủ. Chờ là `flock` chặn (không thăm dò), ai đến trước thường vào trước.
# ponytail: flock không hứa đúng FIFO giữa nhiều lượt cùng chờ; cần thứ tự chặt thì đổi sang hàng đợi vé.
# fd 8 giữ suốt lượt (đi theo `exec` sang python/pytest/bash), nhả khi tiến trình chết — không có khoá treo.

# gate_lock <x|s> <nhãn>: chặn tới khi giữ khoá cổng ở chế độ đã cho.
gate_lock() {
  local mode="$1" who="$2"
  exec 6> /work/gate-turn.lock
  exec 8> /work/gate-full.lock
  if ! flock -n 6; then
    echo "khoá cổng: có lượt đầy đủ xếp trước — chờ" >&2
    flock 6
  fi
  if ! flock -n "-$mode" 8; then
    if [[ "$mode" == x ]]; then
      echo "khoá cổng: chờ các lượt đang chạy xong (lượt đầy đủ gần nhất: $(cat /work/gate-full.owner 2> /dev/null || echo 'không rõ'))" >&2
    else
      echo "khoá cổng: chờ lượt đầy đủ xong — $(cat /work/gate-full.owner 2> /dev/null || echo 'không rõ chủ')" >&2
    fi
    flock "-$mode" 8
  fi
  flock -u 6
  exec 6>&-
  if [[ "$mode" == x ]]; then
    echo "$who từ $(date -u +%H:%M:%SZ)" > /work/gate-full.owner
  fi
}
