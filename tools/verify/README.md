# tools/verify

Cổng verify chạy qua `bash tools/verify/run.sh <việc>` (xem `CLAUDE.md`).

- `verify`: ghi log cổng và `<log>.junit.xml` của bước 5 vào `.cache/src-out/verify/` (NO-324).
- `verify --fast` (PERF-03): bước 1, 2, 4, pytest các đơn vị bị chạm (`fast_test_paths`; đổi `conftest.py`,
  `pyproject.toml`, `uv.lock`, `packages/testing/fixtures/` thì cả bộ), không độ phủ; mypy nền trên cache ấm
  `/work/mypy-fast-<worktree>`. Xem trước — `verify` đầy đủ trước merge vẫn là phán quyết.
- Bước 3: cổng đầy đủ (không `--steps`, hoặc `--steps` gồm **mọi** bước 1–8 và `5b`) chạy mypy
  **nguội** (`MYPY_CACHE_DIR=/dev/null`, ~212 s cả repo); `--steps` thiếu bước và `shell` dùng cache ấm
  `/work/mypy-<worktree>` (~5 s) — chỉ là xem trước: cache ấm có thể phát lại kết quả cũ cả hai chiều.
  Nghi thì `mypy --cache-dir /dev/null` trong `shell` (NO-306).
- Gửi nguồn: `run.sh` dựng `.cache/src-tar/run.<ngẫu nhiên>/src.tar` (mỗi lượt một bản, xoá khi thoát) từ `git ls-files -co --exclude-standard` (đã theo dõi +
  chưa theo dõi không bị ignore), mount `/src-tar:ro`, và `in_container.sh` giải nén vào `/tmp/w` — thay
  `cp -r /src/. /tmp/w` (~3.300 tệp qua mount Windows→WSL2, đo riêng 169 s; nay 13 MB
  đọc một lần — `verify --steps 1` toàn lượt 95 s nguội / 39–42 s ấm → 6 s). Tệp bị `.gitignore` (`.cache/`, `backend/`, `node_modules/`) **không**
  vào `/tmp/w` nữa; thứ cổng cần mà git không theo dõi đi qua mount riêng như trước (`/appfront`,
  `/src-out/contract-samples`, volume `/work`). Gọi compose tay (không qua `run.sh`) thì không có tar và
  `in_container.sh` tự về `cp -r /src`.
- `shell`: làm việc trên **bản chép** `/tmp/w` của worktree. Kết quả sửa trong đó (`ruff --fix`,
  `ruff format`, `python -m packages.db.new_revision`, file mới) **không** về worktree — chép tay ra
  `/src-out/...` như `lock` làm, hoặc sửa ở worktree rồi chạy lại (NO-190).
- Volume `appback-work` (`/work`, dùng chung mọi worktree) là `external`: `run.sh` tự `docker volume create` trước
  mỗi lượt; chạy `docker compose -f deploy/compose/verify.yml` tay trên máy sạch thì phải tạo volume trước (NO-185).
- Repo AppFront mặc định là `<cha của checkout chính>/AppFront`; `APPFRONT_REPO` ghi đè (NO-325).
