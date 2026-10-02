# Review merge fix/b0-05-ml-probe-fixture-modules → main

- Ngày: 2026-10-02 · Reviewer: phiên /merge-review (độc lập, R-37) · Commit đầu nhánh: `b12c3f3d8e5a`
- Phạm vi: `git diff main...b12c3f3` = **một tệp**, `packages/messaging/tests/test_tasks.py` (+43 −3). Đúng whitelist của `FIX-115/spec.md`.
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 1: nhánh đi review, chạm `packages/**`); `bash tools/verify/run.sh verify` **mã thoát 0**, bước 0–8 `đạt` (log `F:/AppBack/backend/dieu-phoi/chay/FIX-115/gate-1.log`, tiêu đề log ghim sha `b12c3f3d8e5a`; `7476 passed` ở bước 5; bước 5b `perf: 0 đơn vị bị chạm`; bước 6/7/8 `đạt`). Không có bước nào `không áp dụng`, không có bước `chưa chạy`. Cổng **không** chạy lại theo yêu cầu điều phối; trạng thái đọc từ bảng E.10 cuối log cộng `mã thoát: 0`.
- Tái hiện độc lập: một `run.sh shell` trên worktree review (detach `b12c3f3`, cây sạch), chạy lệnh tái hiện của spec cộng thêm test hồi quy mới: `pytest -q -p no:randomly apps/ml/objects/tests/test_tasks.py::test_objects_detect__J01 …::test_registered_tasks_finds_tasks_under_the_ml_app …::test_drop_new_ml_modules_keeps_modules_loaded_before_the_snapshot tests/e2e/test_pipeline_e2e.py::test_spatial_read_layer__C01_pipeline` → **4 passed**, `REPRO_EXIT=0` (3 test của spec đạt, cộng 1 test mới). Trên `main` lệnh 3 test này nổ `ValueError: task đã khai` theo `FIX-115/spec.md`. Chỉ một container, chạy sau khi cổng đã kết thúc (`docker ps --filter name=verify-run` = 0).
- Độ phủ: `coverage_gate: đạt` — tổng dòng **99,50%** · nhánh **98,11%**; `packages/messaging` dòng **100,00%** · nhánh **100,00%**; tập file bị chạm dòng **100,00%** · nhánh **100,00%**. Trên ngưỡng 90/90 cho cả gói bị chạm và tổng.

## Điều kiện dừng sớm (§2) — không trúng điều nào
| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` worktree review | rỗng |
| Commit vào main | 1 (`b12c3f3`), không có commit lạ |
| `changes/B0-05.md` | có |
| Dòng đầu commit | `fix(messaging): drop only test-loaded ml modules in probe fixture` — 65 ký tự, đúng mẫu |
| Trailer | `Prompt: B0-05`, `Fix: FIX-115`, `Co-Authored-By:` liền nhau ở cuối thân |
| Tệp cấm (`docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`) | không đụng |
| `pragma: no cover` / `noqa` trần / `type: ignore` / `skip` / `xfail` / hạ ngưỡng | không có (quét diff) |
| `perf` / mã case trong tên test | không có — đúng yêu cầu spec |

## Soát lõi bản sửa

**Gốc chứ không phải triệu chứng (R-19).** Lỗi gốc là hai ảnh chụp lệch pha: `saved = dict(_TASKS)` chụp
*trước* lượt test, còn việc dọn `sys.modules` xoá **mọi** `apps.ml*`, kể cả module đã nạp trước đó mà dòng
`_TASKS` của nó vẫn được trả lại → lần nhập sau chạy lại `define_task` → `ValueError: task đã khai`.
Bản sửa đưa hai ảnh chụp về cùng một thời điểm (`test_tasks.py:635-636`): tên có trong `before` thì giữ cả
module **và** dòng `_TASKS`; tên mới thì xoá cả hai. Hai nhánh nhất quán theo cả hai chiều — đây đúng là
bất biến thiếu, không phải vá chỗ nổ.

**Tốt hơn cách sửa đề xuất trong `DEBT.md` NO-310** ("hẹp lại thành `apps.ml.probe`"): nếu chỉ xoá
`apps.ml.probe`, các module `apps.ml.*` thật do `registered_tasks()` nhập *trong* lượt test sẽ ở lại
`sys.modules` trong khi dòng `_TASKS` của chúng bị gỡ theo `saved` → lượt dò sau không nhập lại được
(module đã cache, `define_task` không chạy) và task thật **mất** khỏi sổ. Cách chụp `before` không có lỗ đó.

**`_TASKS` và `apps.ml.__path__` vẫn trả về** (`:638-639` clear+update; `:631` `monkeypatch.setattr` nên
pytest tự trả `__path__`). Đã đọc tận thân fixture, không chỉ diff.

**Test hồi quy không phụ thuộc thứ tự.** `test_drop_new_ml_modules_keeps_modules_loaded_before_the_snapshot`
tự nhập `apps.ml.objects.tasks` ở `:650` *trước* khi chụp `before` ở `:652`, nên dù chạy đầu tiên trong tiến
trình thì tên đó vẫn nằm trong `before`; không mượn trạng thái của test khác, không dùng fixture
(đúng chỉ dẫn spec: tách `_drop_new_ml_modules` ra hàm thường rồi test trực tiếp). An toàn xdist: chỉ
đụng `sys.modules` của chính tiến trình worker. Tên giả `apps.ml.__fix_115_probe__` được chính lời gọi
`_drop_new_ml_modules` xoá nên không rò sang test sau. Docstring: có ở cả `_drop_new_ml_modules`, hàm lồng
`is_new_ml_module` và test (R-01, R-02).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | MNT-04 (dead code) | `importlib.import_module("apps.ml.objects.tasks")` là no-op: module đã nạp ở `:650`, mà lời gọi lại nằm **sau** `before = set(sys.modules)` nên không làm việc "nạp trước" mà nó gợi ý. Người đọc sau dễ hiểu sai đâu là bước dựng. | `packages/messaging/tests/test_tasks.py:653` | Xoá dòng đó; `assert "apps.ml.objects.tasks" in before` ở `:654` đã chứng minh việc nạp trước. |
| 2 | P3 | TEST-07 (rò trạng thái toàn tiến trình) | Test nhập `apps.ml.objects.tasks` mà **không** lưu/trả `tasks_module._TASKS`. Nếu nó là người nhập đầu tiên trong tiến trình, các dòng task của `apps.ml.objects` ở lại sổ toàn cục sau khi test xong. Hôm nay vô hại — mọi khẳng định về sổ đều là kiểm thuộc về (`:225` `not in`, `:645` `in`) — nhưng một khẳng định "đúng bằng tập X" thêm sau sẽ đỏ theo thứ tự chạy. | `packages/messaging/tests/test_tasks.py:650` | 3 dòng `saved = dict(tasks_module._TASKS)` … `clear()/update(saved)` như fixture đã làm, hoặc dùng luôn một fixture dọn sổ dùng chung. |
| 3 | Nit | TEST | Test đã cài chốt cho *ngữ nghĩa* `_drop_new_ml_modules`, nhưng triệu chứng gốc (`ValueError: task đã khai` sau khi fixture dọn) chỉ được chứng minh bằng lệnh tái hiện rời, không có test nào trong cây giữ nó. Chấp nhận được: spec cấm dạng "test A dùng fixture, test B kiểm" vì phụ thuộc thứ tự, và không có cách dựng lại chuỗi đó mà không tự gây lỗi. | — | Không cần làm. |
| 4 | Nit | TEST | Lỗ còn lại: một module `apps.ml.*` thật **lần đầu** được nhập *trong* lượt test probe (không nhập ở lúc thu test) vẫn bị xoá khi dọn → vẫn thành lớp mới về sau, tức triệu chứng danh tính của NO-310 chưa tắt hẳn về lý thuyết. Thực tế mọi tệp test của `apps/ml` đều nhập mục tiêu ở tầm module, nên chúng luôn có trong `before`. | `:598-611` | Không cần làm; ghi lại ở đây để lần sau có ai gặp lại thì biết chỗ. |

Không có P0, không có P1, không có P2.

## Kiểm sổ nợ (§5)
- `DEBT.md:331` `NO-310` (P2) vẫn `⬜`. **Không** chặn merge: `FIX-115/spec.md` ghi rõ "Không sửa `DEBT.md`
  (điều phối đóng NO-310)" — việc đóng dòng thuộc người điều phối sau khi merge. Nội dung bản sửa đã xử lý
  đúng nguyên nhân mà NO-310 nêu ⇒ **đóng được** sau merge.
- Nhánh không mở nợ mới. Finding 1 và 2 là P3, theo R-34 không bắt buộc dòng `DEBT.md`; nếu điều phối muốn
  theo dõi thì gộp vào một dòng khi B0-05 chạm lại tệp này.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 4 | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 | 0,12 |
| **Tổng** | **100%** | | **4,90 / 5** |

## PHÁN QUYẾT: APPROVE

Bản sửa đánh đúng nguyên nhân: nó biến hai ảnh chụp lệch pha (`_TASKS` chụp trước lượt test, `sys.modules`
xoá sạch theo tiền tố) thành một cặp nhất quán tại cùng một thời điểm, nên cả hai chiều — module cũ giữ danh
tính và giữ dòng sổ, module mới bị xoá cùng dòng sổ — đều đúng. Cách này còn kín hơn phương án ghi trong
`DEBT.md` NO-310. Diff đúng whitelist một tệp, 43 dòng thêm, không đụng tệp cấm, không có pragma/noqa/skip,
docstring đủ cho mọi hàm, test hồi quy tự dựng trạng thái nên không phụ thuộc thứ tự chạy và an toàn xdist.
Cổng đầy đủ mã thoát 0 với 8/8 bước đạt và độ phủ 100/100 cho `packages/messaging`; tôi tái hiện độc lập
được 4 passed. Không có P0, P1 hay P2; chỉ hai P3 nhỏ về dòng chết và rò dòng sổ `_TASKS` trong test mới,
cùng hai Nit ghi để tham khảo — không điều nào chặn merge. **Được merge vào `main`.** Hai P3 nên gom vào lần
sau B0-05 chạm `packages/messaging/tests/test_tasks.py`; người điều phối đóng `DEBT.md` NO-310 sau khi merge.
