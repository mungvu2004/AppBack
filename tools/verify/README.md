# tools/verify

Cổng verify chạy qua `bash tools/verify/run.sh <việc>` (xem `CLAUDE.md`).

- `verify`: ghi log cổng và `<log>.junit.xml` của bước 5 vào `.cache/src-out/verify/` (NO-324).
- `shell`: làm việc trên **bản chép** `/tmp/w` của worktree. Kết quả sửa trong đó (`ruff --fix`,
  `ruff format`, `python -m packages.db.new_revision`, file mới) **không** về worktree — chép tay ra
  `/src-out/...` như `lock` làm, hoặc sửa ở worktree rồi chạy lại (NO-190).
- Volume `appback-work` (`/work`, dùng chung mọi worktree) là `external`: `run.sh` tự `docker volume create` trước
  mỗi lượt; chạy `docker compose -f deploy/compose/verify.yml` tay trên máy sạch thì phải tạo volume trước (NO-185).
- Repo AppFront mặc định là `<cha của checkout chính>/AppFront`; `APPFRONT_REPO` ghi đè (NO-325).
