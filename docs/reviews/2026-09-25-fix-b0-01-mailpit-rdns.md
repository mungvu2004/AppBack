# Review merge fix/b0-01-mailpit-rdns → main

- Ngày: 2026-09-25 · Reviewer: phiên /merge-review (worktree riêng `review-fix106`, không sửa mã, không merge)
- Commit đầu nhánh: `5ac987baa6fa` · `git log main..HEAD` = 1 commit · `git status --porcelain` rỗng
- Phạm vi: `packages/testing/fixtures/services.py` (+7 / −1), đúng whitelist `docs/fixes.md` FIX-106 [4]
- Cổng: `bash tools/verify/run.sh verify` mã thoát **0** (log: `…/Temp/claude/C--Users-mxuan-orca-workspaces-AppBack-review-fix106/verify-fix106.log`, dòng `EXIT=0`)
  - 8/8 bước `đạt` (0 làm ấm node_modules · 1 ruff format · 2 ruff check · 3 mypy --strict · 4 lint-imports · 5 coverage+pytest → coverage_gate · 5b perf → case_gate · 6 lint_migrations+migrate_check · 7 H1 H3 H4 H5 · 8 openapi). H4 "không áp dụng" — B3-05 chưa hợp nhất, đúng BE-00 §12.
  - Pytest: **4011 qua, 0 hỏng**, 4 deselected, 23 phút 36 s
- Độ phủ: tổng dòng **99,45 %** · nhánh **98,33 %** — `packages/testing` dòng 99,51 % · nhánh 98,95 % — tập file bị chạm 100 % / 100 %

## Kiểm chứng độc lập (không tin báo cáo tác giả)

| Khẳng định | Cách kiểm | Kết quả |
|---|---|---|
| Sửa đúng nguyên nhân gốc (rDNS), không nới timeout/skip | đọc toàn bộ `git diff main...HEAD` | đúng — chỉ thêm `.with_env("MP_SMTP_DISABLE_RDNS", "true")` + docstring; không chạm `packages/mail/**`, `SMTP_TIMEOUT_S`, không chạm một test nào |
| Env đúng tên cho ảnh ghim `axllent/mailpit:v1.20.0` | `docker run --rm axllent/mailpit:v1.20.0 --help` → `--smtp-disable-rdns  Disable SMTP reverse DNS lookups`; và `grep -ao "MP_SMTP_DISABLE_RDNS" /mailpit` trong chính ảnh ghim | đúng — cả cờ và biến môi trường đều có trong nhị phân v1.20.0 |
| Không có `pragma: no cover` / `noqa` trần / `skip` / `xfail` / hạ ngưỡng | `git diff main...HEAD \| grep -n "pragma\|noqa\|type: ignore\|skip\|xfail"` | rỗng |
| Commit hợp lệ | dòng đầu `fix(testing): disable mailpit rdns lookups in the test fixture` (58 ký tự), trailer `Prompt: B0-01` + `Fix: FIX-106` | đạt |
| 5 test thư từng hỏng nay xanh | log bước 5: `packages/mail/tests/test_fixtures.py .......` · `test_sender.py .....................` · `apps/api/auth_recovery/tests/test_e2e.py ..` · `tools/tests/test_services.py ..............` | **cả 5 xanh**, kể cả 2 test e2e mà tác giả báo vẫn hỏng |
| Test không còn phụ thuộc DNS của máy | Mailpit không tra PTR nữa ⇒ không còn lệnh gọi DNS nào trên đường SMTP của test | đạt |
| Nợ có sổ | `DEBT.md` NO-210 (P1, 🔧) + `docs/fixes.md` FIX-106 [1]–[6] có lỗi, nguyên nhân, số đo | đạt (ô [7] "điền khi gộp" là việc của người điều phối) |

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | MNT-02 / R-07 | Cùng khiếm khuyết còn ở hai định nghĩa Mailpit khác: stack compose chạy đúng ảnh ghim ấy mà **không** tắt rDNS, nên bất kỳ lượt gửi thư qua stack (e2e/smoke thủ công, dev) trên máy có PTR chậm vẫn treo ~10 s như NO-210. Cổng đầy đủ không bị ảnh hưởng: `deploy/compose/verify.yml` không có mailpit, bước 5 dựng Mailpit qua testcontainers (đường đã sửa) | `deploy/compose/ci.yml:52`, `deploy/compose/dev.yml:55` | Ngoài whitelist FIX-106 [4] nên **không** chặn nhánh này: ghi một dòng `DEBT.md` để chủ `deploy/compose/*` thêm `MP_SMTP_DISABLE_RDNS: "true"` vào hai service |
| 2 | Nit | MNT-06 | Docstring nêu lý do rất tốt nhưng không ràng tên env vào **phiên bản ảnh**; nâng `MAILPIT_IMAGE` mà env bị đổi tên thì fixture âm thầm quay lại rDNS (thử lại 10 s/thư) chứ không báo lỗi. Fixture láng giềng `_via_mapped_port` có đúng dạng cảnh báo này ("nâng testcontainers thì chạy lại …") | `packages/testing/fixtures/services.py:98-102` | Thêm một câu: env này có từ Mailpit v1.x — nâng `MAILPIT_IMAGE` thì kiểm lại `--help \| grep rdns` |
| 3 | Nit | TEST-07 | Báo cáo tác giả nêu một "nguyên nhân gốc thứ hai" cho 2 test e2e (`Received unregistered task default.auth_recovery.send_token_mail`) và báo `outcome failed`. Kiểm lại: trong **cổng đầy đủ** cả 2 test đều xanh. Đó là hệ quả của việc chạy một **tập con** test — `send_token_mail` chỉ vào registry khi có module nào nhập `apps/api/auth_recovery/jobs.py` (`shared_task` trong `define_task`, `packages/messaging/tasks.py:343`), mà `test_e2e.py` không nhập `jobs`; chạy cả bộ thì `test_jobs.py` nhập hộ. Đây là điểm yếu cách ly test **có sẵn**, không do nhánh này, và không đỏ cổng | `apps/api/auth_recovery/tests/test_e2e.py:1-40` (đã có), `packages/messaging/tasks.py:343` | Không sửa trong nhánh này. Nếu muốn chạy tập con lặp lại được: một dòng `DEBT.md` cho chủ `auth_recovery` để `test_e2e.py` tự nhập module task nó cần |
| 4 | Nit | — | Trailer `Co-Authored-By: Claude <noreply@anthropic.com>`, mẫu hiện hành là `Claude Opus 5 <noreply@anthropic.com>`. Hook `commit-msg` chỉ soát dòng đầu nên không hỏng gì | commit `5ac987b` | Để nguyên (viết lại history không đáng); dùng đúng chuỗi ở commit sau |

Không có finding P0, P1 hay P2. Nợ P1 duy nhất đang mở liên quan (NO-210) **chính là** nợ nhánh này trả, nên không chặn merge theo R-35/R-38.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |
| **Tổng** | **100 %** | | **4,90 / 5** |

TEST và MNT hạ xuống 4 vì finding 1 và 3 (đều P3/Nit, đều ngoài whitelist của FIX-106); các miền còn lại không có finding — diff chỉ tắt một lượt tra DNS trong container test, không chạm mã nghiệp vụ, không chạm hợp đồng, không chạm migration.

## PHÁN QUYẾT: APPROVE

Sửa đúng tầng gốc: nguyên nhân là Mailpit tra PTR của client trước lời chào SMTP, và nhánh này tắt đúng cái đó ở container test bằng biến môi trường **đã kiểm chứng có trong nhị phân ảnh ghim v1.20.0** — không nới `SMTP_TIMEOUT_S`, không `skip`, không chạm `packages/mail/**` hay một test nào. Diff một dòng hiệu lực, docstring nói rõ vì sao, và cổng đầy đủ tự chạy tại chỗ cho mã thoát 0 với 4011 test qua, 0 hỏng — cả 5 test thư mà NO-210 nêu đều xanh, gồm 2 test e2e mà tác giả tưởng còn đỏ (thực ra chỉ đỏ khi chạy tập con). Độ phủ vượt ngưỡng ở mọi mức. Bốn điểm ở trên là nhận xét, không phải điều kiện: người điều phối nên ghi `DEBT.md` cho finding 1 (rDNS còn bật trong `deploy/compose/ci.yml`, `dev.yml`) và đóng NO-210 + điền `docs/fixes.md` FIX-106 [7] khi gộp.
