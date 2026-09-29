# Review merge fix/b6-02-build-fence → main

- Ngày: 2026-09-29 · Reviewer: phiên /merge-review (FIX-113, độc lập tác giả) · Commit đầu nhánh: `c7c90495769e`
- Phạm vi: `git diff main...c7c9049` — 4 file, +118/−5: `apps/worker/datasets/{tasks,render}.py`
  + `apps/worker/datasets/tests/{test_tasks,test_render}.py`. Cây làm việc sạch, một commit, dòng đầu đúng
  Conventional Commits, có trailer `Prompt: B6-02` + `Fix: FIX-113`. `changes/B6-02.md` đã có.
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 1 — lượt review đầu của nhánh; tác giả cũng chạy đầy đủ, không cần chạy lại).
  `bash tools/verify/run.sh verify` **mã thoát 0**, 8/8 bước `đạt` (0,1,2,3,4,5,5b,6,7,8); 6368 passed / 547 s.
  Log: `backend/dieu-phoi/chay/B6-02/fix113-gate.log`, trỏ log trong container
  `20260929T062628Z-c7c90495769e.log` → **đúng sha** `c7c9049`. Không bước nào "không áp dụng", không bước nào bỏ.
- Độ phủ: tổng dòng **99.56%** · nhánh **98.45%**; `apps/worker/datasets` dòng **100.00%** · nhánh **100.00%**;
  tập file bị chạm 100.00%/100.00% — `coverage_gate: đạt`. Không `pragma: no cover`, không `type: ignore`,
  không `noqa`, không `skip`/`xfail` mới trong diff (K24 sạch).

## Đã tự kiểm (không tin báo cáo tác giả)

1. **Rào đúng chỗ và đủ (NO-273).** `grep` mọi lượt ghi kho trong `tasks.py`: `writer.add_sample` → `_put`
   gọi `before_put` (`writer.py:95`), `writer.finish` gọi `before_put` trước `put` (`writer.py:114`),
   `delete_prefix` dọn đầu lượt (`tasks.py:493`) **nay** có `await fence.check()` ngay trên nó. Sau vá,
   **không còn lượt ghi kho nào của đường thành công nằm ngoài rào**. `fence.check()` = `lock.renew(token)`
   → `_StoppedError`, bị `run_build_dataset_version` bắt và chỉ log, nên bản vẫn `building` cho lượt chủ khoá
   thật — đúng bất biến số 1.
2. **Test cướp khoá rơi đúng khe `_claim` (không phải khe giả).** `SafeLock` đặt khoá tại `lock:{name}`
   (`packages/messaging/locks.py:68`), tức `lock:datasets:build:{dsv}` — chính key mà `_ClockThatStealsTheLock`
   xoá. `clock.now()` đầu tiên của một lượt dựng đúng là dòng `now = clock.now()` trong `_claim`
   (`tasks.py:431`); `SafeLock.hold` không nhận `Clock` nên không có lời gọi `now()` nào trước đó. Test khẳng
   định `build_started_at is not None` (đã qua `_claim`) **và** `status == "building"` **và** object của lượt kia
   còn nguyên — nếu lượt xoá key thất bại thì lượt dựng sẽ chạy tiếp và `delete_prefix` xoá `rival_key`, tức
   test tự chứng minh nó dừng trong khe cần kiểm, không phải xanh vì lý do khác.
3. **Mock/fake đúng tầng (K23).** Test dùng Postgres thật (`db_sessionmaker`), Redis thật (`safe_client` async
   + `safe_redis_sync()` cho lượt xoá đồng bộ, **không** `fakeredis`), `LocalDiskStorage` thật. Chỉ `Clock` bị
   bọc — đúng tầng được phép fake. Key bị xoá có phạm vi theo `version_id` nên test chạy song song được.
4. **`.get()` không nuốt lỗi khác (NO-274).** `dict.get` chỉ che đúng "thiếu khoá"; không `try/except`, không
   bắt `Exception`. Cả hai chỗ (`render.py:124` `wall_mask`, `:163` `object_boxes`) bỏ **đúng một ô mở** rồi vẽ
   tiếp, không bỏ tường/đồ đạc — ba test phủ: ô mồ côi lẫn ô thật (mặt nạ pixel giống hệt ca không có ô mồ côi),
   hộp còn `["door","table"]`, và ca biên mọi ô mở đều mồ côi vẫn trả hộp đồ đạc. Không còn `walls_by_id[...]`
   tra trực tiếp nào trong file. Comment đổi tên biến `host` giải thích **tại sao** (R-03) đúng chỗ.
5. **Sửa gốc, không vá triệu chứng (R-19).** Cả hai vá đặt ở đúng hàm mà mọi người gọi đi qua; không thêm
   abstraction, không thêm cờ cấu hình (R-10). Docstring module `render.py` nêu bất biến mới, docstring mỗi
   hàm/lớp mới có (R-01, R-02).

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | CON-04 | Hai lượt `delete_prefix` của đường **thất bại** vẫn ngoài rào: `_finish` khi `finish_version` trả `False` và trạng thái đọc lại là `failed`, và `run_fail_dataset_version`. Hôm nay vô hại — không có đường nào đưa một bản `failed` trở lại `building` (`versions.py:70` chỉ đặt `building` lúc INSERT), nên không có lượt khác đang ghi dưới tiền tố đó. Ngoài diff FIX-113. | `apps/worker/datasets/tasks.py:465`, `:555` | Ghi một comment nêu điều kiện an toàn ("`failed` là trạng thái cuối, không quay lại `building`") để lần sau đọc không phải suy lại; không cần rào. |
| 2 | P3 | R-34 | `NO-273`, `NO-274` trong `DEBT.md:294-295` vẫn `⬜ … mở`, dù bản vá nằm trong nhánh này. | `DEBT.md:294`, `:295` | Phiên gộp đóng hai dòng (✅ + sha `c7c9049`) ngay sau merge; reviewer không sửa `DEBT.md` theo phạm vi task. |
| 3 | Nit | TEST-09 | `_ClockThatStealsTheLock.now()` gọi Redis **đồng bộ** trong vòng sự kiện (một `DEL`, ~ms). Docstring đã nêu lý do (`now()` là hàm đồng bộ) và đây là cách duy nhất chen vào khe mà không gọi hàm private — chấp nhận được trong test. | `apps/worker/datasets/tests/test_tasks.py:923-929` | Không cần sửa. |
| 4 | Nit | R-01 | `_ClockThatStealsTheLock.__init__` không có docstring — nhưng lớp có, thân chỉ là gán, và `_Beat.__init__` cùng module cũng vậy: đúng quy ước sẵn có. | `test_tasks.py:912` | Không cần sửa. |

Không có P0, không có P1.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1.25 |
| CON – Concurrency & dữ liệu | 15% | 4 | 0.60 |
| LOG – Tính đúng đắn | 15% | 5 | 0.75 |
| PERF – Hiệu năng | 10% | 5 | 0.50 |
| RES – Chịu lỗi | 10% | 5 | 0.50 |
| DB, API – Migration & contract | 10% | 5 | 0.50 |
| TEST – Kiểm thử | 7% | 4 | 0.28 |
| OBS, OPS – Vận hành | 5% | 5 | 0.25 |
| MNT – Bảo trì | 3% | 4 | 0.12 |
| **Tổng** | **100%** | | **4.75 / 5** |

## PHÁN QUYẾT: APPROVE

Hai bản vá nhỏ, đúng gốc, đúng phạm vi hai dòng nợ được giao. Bất biến "mất khoá → không ghi, không finish,
**không** `delete_prefix`" nay khép kín trên đường thành công: tôi đã liệt kê mọi lượt ghi kho trong `tasks.py`
và `writer.py`, cả bốn đều sau một `fence.check()`. Test cướp khoá là loại test đúng — Redis/Postgres/kho thật,
chen vào khe `_claim` thật qua điểm `clock.now()` đầu tiên, và tự vô hiệu nếu lượt xoá key không ăn. `.get()`
chỉ che thiếu khoá và bỏ đúng một ô mở, có cả ca biên "mọi ô mở mồ côi". Cổng đầy đủ mã thoát 0, 8/8,
`apps/worker/datasets` 100%/100%, không dấu hiệu né cổng. Ba finding còn lại là P3/Nit không chặn merge:
đóng `NO-273`/`NO-274` trong `DEBT.md` khi gộp là việc duy nhất phải làm kèm.
