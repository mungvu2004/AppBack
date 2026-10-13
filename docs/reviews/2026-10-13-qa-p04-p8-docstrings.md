# Review merge qa/p04-p8-docstrings → main

- Ngày: 2026-10-13 · Reviewer: phiên /merge-review · Commit đầu nhánh: b100e98cce06 (base `main` 1e2bd91da6ae = merge-base, `main` chưa đi tiếp)
- Cổng: phạm vi đầy đủ — lượt 1 của nhánh (R-33b đk 1); `bash tools/verify/run.sh verify` mã thoát 0
  (log: `.cache/src-out/verify/20261013T115248Z-b100e98cce06.log` — sha trong tên trùng HEAD; bước 0–8 `đạt`,
  `8448 passed` ở bước 5, `4 passed` perf ở 5b, `case_gate: đạt`, `migrate_check: đạt`, bước 7 H1/H3/H4/H5 `đạt`, `mã thoát: 0`;
  log bọc `scratchpad/verify-qa-p04-r2.log` kết thúc `EXIT=0`). Không chạy lại (đọc log, theo yêu cầu phiên gọi).
- Độ phủ: tổng dòng 99,47% · nhánh 98,04% — gói bị chạm `apps/api/{floors,project_settings,quality,spatial_read,spatial_write}`
  100%/100%, `apps/api/core` 99,92%/99,65%; tập file bị chạm 100%/100%.

## Phạm vi

3 commit, trailer `Prompt: QA-04c` đủ, dòng đầu đúng Conventional Commits:
`ba926f15 test(spatial): tag phase 04 catalog rows in docstrings` (13 tệp test, +148/−36),
`d5d19840 docs(changes): add QA-04c change note…` (`changes/QA-04c.md`), `b100e98c docs(debt): log NO-422…` (`DEBT.md` +1 dòng).

Điều kiện dừng sớm: cây sạch; `changes/QA-04c.md` có; không file cấm; không `pragma`/`type: ignore`/`noqa`/`skip`/`xfail`
mới → không áp dụng.

## Kiểm độc lập

- **Chỉ docstring (cơ học):** với mỗi tệp `.py` đổi, parse AST ở `main` và `HEAD` (Python 3.13), xoá chuỗi docstring của mọi
  module/class/hàm rồi so `ast.dump` → **13/13 giống hệt**. Lọc `git diff main...HEAD -- apps/` theo dòng `+`/`-`: mọi dòng
  đều là văn bản docstring (`Hàng catalog: […]`, dòng trống, đóng/mở `"""`). Không đổi assert, fixture, marker, tên test.
- **Đối chiếu catalog** (`backend/dieu-phoi/chay/QA-04c/catalog-C*.md`, cột `existing`; danh sách gắn ở `flow-plan.md`
  §"AppBack pytest" PY-01…): 55 mã trên 41 hàm test, mỗi mã đúng **một** docstring trong toàn `apps/`+`packages/`;
  **55/55** tên test nằm trong cột `existing` của đúng hàng đó; tập mã gắn = tập mã kế hoạch giao cho pytest (56 mã nhắc trong
  mục đó, trừ `BE4-G-011` thuộc danh sách `n/a`). 4 hàng `be` còn lại có `py:` nhưng không gắn (`BE4-G-032/113`, `BE5-G-024/025`)
  đều `n/a`, không có trong `coverage-ids.txt` — đúng.
- **Soi thân test** (6 mẫu): `test_common__C05` (token rác → 401, BE4-G-002), `test_spatial_write_layer__C14` (hai giao dịch
  thật song song → `[200, 409]`, BE4-G-317), `…returns_503_after_losing_every_race` (503 `DEPENDENCY_UNAVAILABLE` +
  `Retry-After: 1`, BE4-G-056/218) chứng minh đủ hàng. `test_spatial_read_floor__C01`, `test_settings_read_settings__C01`,
  `test_read_view__deleted_floor_is_left_out` chỉ chứng minh mệnh đề đầu của hàng nhiều mệnh đề (finding 1).
- **Cổng FE đọc được thẻ:** `AppFront/qa/tools/coverage-gate.mjs:29` tìm chuỗi `[<id>]` trong mọi `test_*.py` → khuôn
  `Hàng catalog: [BE4-G-xxx]` khớp.
- **NO-422:** log lượt hỏng (`.cache/src-out/verify/20261013T113726Z-fb789ffefdbc.log`, tip trước rebase) có
  `FAILED packages/messaging/tests/test_redis.py::test_a_dead_redis_costs_exactly_the_configured_number_of_retries`,
  `1 failed, 8447 passed`; traceback qua `test_redis.py:172 admin.shutdown(nosave=True)` → `connect_check_health` →
  `on_connect_check_health` (đọc bắt tay) → `redis.exceptions.TimeoutError` — khớp mô tả dòng nợ. Nhánh không chạm
  `packages/messaging`; lượt tip xanh 8448/8448 → có sẵn, không do nhánh. Mức P3 nhất quán với tiền lệ test chập chờn dưới tải
  (NO-403, NO-404, NO-410 đều P3); có chủ (B0-05), hướng sửa gốc, cấm nới assert/retry (K24); id NO-422 không trùng nhánh nào
  (đã quét `DEBT.md` mọi ref). Đủ cho R-34.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | MNT-04 | Thẻ trỏ test chỉ chứng minh một phần hàng nhiều mệnh đề: BE4-G-207/307 ("member 200; non-member 404; bad floor 404") gắn vào test chỉ đọc 200 của thành viên; BE4-G-220 ("viewer mặc định; non-member 404; dự án xoá 404") gắn vào `__C01` (404 ở `__C06`/`__C08`); BE5-G-020 ("bỏ tầng xoá; thứ tự theo order") — thứ tự ở `…two_drawn_floors_by_order_and_focus`. Phép kiểm vẫn có đủ trong bộ test (catalog liệt kê), nên chỉ là truy vết thiếu chính xác: người đọc docstring tưởng một test là đủ bằng chứng. Do luật kế hoạch "một mã đúng một docstring". | `apps/api/spatial_read/tests/test_routes_floor.py:23`, `apps/api/project_settings/tests/test_routes_read.py:21`, `apps/api/quality/tests/test_read_view.py:106` | Lần chạm sau: thêm nửa câu "(phần 404 ở `__C06`/`__C08`)" vào docstring đã gắn, không lặp mã `[…]`. Không chặn, không cần dòng DEBT. |
| 2 | Nit | MNT-04 | Đếm sai: thân commit `ba926f15` và `changes/QA-04c.md` ghi "55 pytest cases"/"docstring của 55 test", thực tế 55 **mã hàng** trên **41** hàm test; scope `test(spatial)` trong khi nhánh chạm cả `core`, `floors`, `project_settings`, `quality`. | `changes/QA-04c.md:4`, commit `ba926f15` | Sửa câu thành "55 mã hàng trên 41 test" nếu còn chạm tệp; commit để nguyên (gộp squash). |
| 3 | Nit | R-34 | Dòng NO-422 không dẫn đường log lượt hỏng (tiền lệ NO-403/NO-404 có), nên phiên DEBT sau phải tự tìm traceback. | `DEBT.md:442` | Thêm `log .cache/src-out/verify/20261013T113726Z-fb789ffefdbc.log` khi đợt DEBT kế nhận dòng này. |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |

Tổng: 4,97 / 5

P0: 0 | P1: 0 | P2: 0 | P3: 1 | Nit: 2

## PHÁN QUYẾT: APPROVE

Nhánh chỉ đổi văn bản docstring (AST 13/13 tệp giống hệt sau khi xoá docstring), 55/55 thẻ trỏ đúng test mà catalog ghi là
bằng chứng của hàng, mỗi mã đúng một docstring, khuôn thẻ khớp `coverage-gate.mjs`. Cổng đầy đủ ở đúng tip `b100e98cce06`
mã thoát 0, độ phủ tổng 99,47%/98,04%. Lỗi đỏ ở lượt đầu là test Redis chập chờn có sẵn, đã có dòng NO-422 P3 đủ chứng cứ và
hướng sửa gốc. Không P0/P1/P2; finding P3 và 2 Nit không chặn merge. Việc merge thuộc phiên gọi.
