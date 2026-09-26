# Review merge feature/b2-05b-quality-api → main

- Ngày: 2026-09-26 · Reviewer: phiên /merge-review (độc lập, R-37) · Commit đầu nhánh: `73066fbddfae`
- Worktree review riêng tại `73066fb`, cây sạch, không sửa mã, không merge.
- Cổng: `bash tools/verify/run.sh verify` mã thoát **0** (chạy tại chỗ trong worktree review, 2026-09-26; log giữ ở scratchpad phiên: `verify-b2-05b.log`). Trần 2 container `verify-run`: 0 container khác lúc bắt đầu.
- Độ phủ (`tools.coverage_gate`, số của lượt chạy này): tổng dòng **99,52%** · nhánh **98,44%** · `apps/api/quality` **100,00% / 100,00%** · `packages/db` 96,39% / 95,69% · tập file bị chạm 100,00% / 100,00%.
- Test: **4729 passed, 7 deselected** (1205 s); bước 5b perf **3 passed** (29 s).

## Bảng cổng (mã thoát thật, dán nguyên)

| bước | lệnh | trạng thái | ghi chú |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | 9 contract kept, 0 broken |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 4729 passed / 7 deselected |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf 3 test |
| 6 | `lint_migrations` → `migrate_check` | đạt | 12 revision · 1 head · downgrade/upgrade/base/model-khớp-DB đều đạt |
| 7 | H1 H3 H4 H5 | đạt | H1 đạt 1198 mẫu · H1 ngữ cảnh đạt 50 mẫu · H3 đạt · **H4 không áp dụng** (B3-05 chưa hợp nhất — đúng điều kiện BE-00 §12) · H5 đạt · Smoke/Bản đồ đạt |
| 8 | `openapi` | đạt | |

`case_gate` cho ba `op` của prompt: `quality_read_assessment` **đạt** · `quality_set_corners` **đạt** (thừa C14, J09, U03, U07) · `quality_straighten` **đạt**. C16 miễn ở cả hai `op` ghi POST, lý do trong `apps/api/quality/cases.toml` đứng được (thân chỉ có toạ độ số / thân rỗng, không có chuỗi người nhập).

## Phạm vi đã đọc

`git diff main...HEAD`: **29 file, 4458 dòng thêm, 0 dòng xoá**. Nguồn ≈ 1.197 dòng (`apps/api/quality/*.py` 1.109 + `packages/db/models/quality.py` 33 + revision 55), test ≈ 2.261 dòng, `changes/B2-05b.md` 11, `docs/contracts/openapi.json` 489 (commit `docs(contract)` của điều phối viên).

Không có điều kiện dừng sớm: cây sạch · `changes/B2-05b.md` có · 6 commit đều đúng Conventional Commits ≤ 72 ký tự + trailer `Prompt: B2-05b` · không đụng `docs/charter/*`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `conftest.py` gốc, `pyproject.toml` gốc, `.importlinter` · `docs/contracts/openapi.json` **thuần thêm** (0 dòng xoá) và chỉ thêm đúng ba đường `…/quality`, `…/quality/corners`, `…/quality/straighten` · không `pragma: no cover` / `pragma: no branch` · `# type: ignore[arg-type]`, `[list-item]` và `# noqa: S603` đều có mã kèm lý do · không `except Exception` rộng · không `skip`/`xfail` mới · không hạ ngưỡng.

## Những gì đã đối chiếu tận mã (không tin báo cáo)

- **Hợp đồng #30–#32 vs `src/api/schemas/quality.ts`** — `QualityAssessmentOut`/`FloorQualityOut`/`FindingOut`/`RegionOut`/`MeasurementOut`/`FrameOut` khớp `ImageQualityAssessmentSchema` `.strict()`; `WireModel` bỏ trường `None` nên không `null` trên dây (test `"null" not in response.text` ở C17 của cả ba `op`); `expectedConfidence` không khai ở đâu; `floorId` luôn thuộc `floors` (`assessments.py:274`) và có test tầng chưa tải trỏ về phần tử đầu; `findings` chỉ 5 mã, mã lạ bị bỏ + log `quality_unknown_code` (`assessments.py:87-88`).
- **`finding.id`** (`assessments.py:191-215`) — `"{level_id}.{code}.{n}.{u}"`, `n` đếm từ 1 trong từng mã theo `(yRatio, xRatio)`, `u` là ULID cuối của `pageKey`. Ổn định giữa các lượt đọc và hai lượt `save_assessment` cùng trang, đổi sau #31/#32 (khoá trang mới), không trùng giữa tầng — cả bốn tính chất đều có test riêng (`test_read_view.py:115,134`, `test_routes_straighten.py:72`).
- **Quyền [7]** — người ngoài kể cả admin hệ thống → 404 `project` (C06 của cả ba `op`); `get_floor` lọc `project_id` nên tầng dự án khác → 404 `floor`; viewer → 403 ở #31 và #32 (C07 cả hai).
- **Luồng #31/#32 [6]** — `await db.rollback()` **trước** khi đọc storage và xử lý ảnh (`service.py:282`, K36), có test pool 1 kết nối khẳng định `engine.pool.checkedout() == 0` trong lúc `deskew` chạy và #30 vẫn trả lời (`test_queue.py:128`). Semaphore theo vòng sự kiện qua `WeakKeyDictionary` (`processing.py:42,64-71`), `ThreadPoolExecutor` riêng `quality-imaging` dựng lười (`processing.py:56-61`), 503 `Retry-After: 2` phát **trước** khi gửi việc (`processing.py:88-90`), `release` trong `finally` (`processing.py:93-94`), `wait_for` chỉ quanh `acquire()` chứ không quanh `run_in_executor` — đúng K28 và BE-00 §7. `put` khoá mới trước giao dịch (`service.py:293`), object bên thua bị xoá (`service.py:301`, test C14 khẳng định còn đúng 2 object trang).
- **Thứ tự khoá BE-00 §7** — `_load_state(locked=True)`: `get_floor(for_update)` → `uploads` FOR UPDATE → `current_drawing(for_update)` → `load_assessment(for_update)` → rồi mới `start_run` (`service.py:127-139`, `service.py:238-241`). Chèn dòng `quality_assessments` mới sau `touch_project` nằm trong ngoại lệ mà §7 nêu (người gọi đang giữ `floors … FOR UPDATE`). Khoá `uploads` không `ORDER BY` nhưng không khoá chéo được vì mọi người ghi đều phải giữ dòng `floors` trước.
- **Kiểm lại bước 2 trong giao dịch cuối** — `_commit_swap` gọi lại `_load_state(locked=True)` nên `_check_editable` ném lại đúng lỗi của bước 2, rồi so `(drawing_id, page_key)`; `None` của `upsert_drawing` **hoặc** `save_assessment` → 409 + rollback huỷ cả `start_run`, có test tham số hoá cho cả hai hàm (`test_routes_corners.py:532`) và test J09 khẳng định hàng `pipeline.cpu` của Redis **thật** rỗng.
- **Hình học** — `validate_corner_ratios` kiểm 4 điểm, miền `[0,1]`, lồi + không tự cắt + thuận chiều kim đồng hồ bằng bốn tích có hướng cùng dấu, điểm đầu là TL, diện tích dây giày ≥ ngưỡng; `to_unrectified` nhân nghịch đảo homography, chặn ma trận suy biến và điểm ra vô cực → 409. Nhánh undo (client cũ ở `7dccb44`) khớp `undo.corners` trong `QUALITY_CORNER_EPS` rồi dùng kích thước + homography của **trang trước** nên không nắn chồng — test so ảnh cuối với ảnh dựng thẳng từ C0 (sai lệch trung bình ≤ 1 px). #32 dùng `compose(H_deskew, H_cũ)`; homography lưu lệch kích thước → 409 (`test_routes_straighten.py:129`).
- **Lỗi** — `VisionError` → `to_app_error()` 422 đúng mã (`IMAGE_TOO_LARGE`, `FILE_CORRUPT` có test U03/U07 ở cả tầng `processing` lẫn tầng route); `VALIDATION` từ `Homography.from_json` (`geometry.py:103-108`) và từ `compose` (`processing.py:131-134`) → 409 `QUALITY_DRAWING_CHANGED`; `QUALITY_LAYER_REVIEWED` 422 chỉ khi `has_human_geometry` **và** upload của bản vẽ có lượt `completed` (`service.py:112-116`), có test cả nhánh "bản vẽ mới chưa `completed` → #32 200"; 409 khi upload `complete` mới hơn mà lượt mới nhất chưa `failed`, và test khẳng định lượt của lần tải mới **giữ nguyên** rồi mở lại được sau khi nó `failed`.
- **`save_assessment`** dùng `lock_run` của B2-04 chứ không chép lại luật, và còn tự kiểm `run.floor_pk` + `drawing.upload_id == run.upload_id` (`assessments.py:143-148`) — đúng BE-00 §7 "Không tin `apps/ml`". Test lượt cũ khẳng định `None` và `corners` người dùng không bị đè.
- **Ranh giới import** — bước 4 `lint-imports` 9/9 kept; thêm test tiến trình mới nhập `apps.api.quality.assessments` khi chặn `fastapi`, `starlette`, `jwt`, `argon2`.
- **Migration DB-01..05** — expand thuần một bảng mới, PK `floor_pk` + FK `floors.pk ON DELETE CASCADE` đúng [5], `drawing_id` cố ý không FK, `downgrade` có, `lint_migrations` 12 revision đạt, `migrate_check` 1 head + upgrade/downgrade/base/upgrade lại/model khớp DB/tên CHECK khớp đều đạt; có test `test_floor_delete_cascades_assessment`.
- **Test** — Postgres, Redis, MinIO và ảnh đều **thật** (không mock dịch vụ nào, K23); `monkeypatch` chỉ chạm hàm cấp module của B2-05a và biến môi trường, đúng như đính chính của điều phối viên. Ma trận [8] đủ: C10 riêng `_queue_once`/`_no_key_replay` đọc hàng Redis thật cho cả hai `op`; C14 đua; K36; hàng 2 chạy / 3 lần 503 chạy **hai** vòng sự kiện; U03/U07; J09; perf PDF A1 và quét 40 MP đều < 15 s.
- **R-01 docstring** — quét toàn bộ 14 file nguồn + test: **không thiếu docstring nào** (module, lớp, hàm, kể cả hàm lồng). Đáng ghi nhận vì `ruff` của repo không bật nhóm `D`, tức đây là kỷ luật tự giác chứ không phải cổng ép.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG-03 | `_ULID.findall(report["pageKey"])[-1]` không có chốt chặn: một `pageKey` không chứa đoạn Crockford 26 ký tự nào sẽ ném `IndexError` → 500 thay vì một lỗi đọc được. Mọi người ghi hiện tại (`new_page_key`, `keys.upload_page`) đều sinh ULID nên chưa với tới được — đây là phòng thủ thiếu, không phải lỗi đang sống. | `apps/api/quality/assessments.py:198` | Rơi về cả `page_key` (hoặc một băm ngắn của nó) khi không tìm thấy ULID; thêm một test dòng đo có `pageKey` lạ. |
| 2 | P3 | LOG-01 | Luật "điểm đầu phải là TL" dùng `min(x + y, x)`. Với tứ giác xoay ≈ 45° (hình thoi) hai đỉnh hoà nhau ở `x + y`, tie-break theo `x` nhỏ hơn chọn đỉnh trái, nên một bộ góc **đúng chiều kim đồng hồ** vẫn bị 422 `VALIDATION field="corners"`. Ví dụ `(0.5,0) (1,0.5) (0.5,1) (0,0.5)` → 422. `_crosses` đã bảo đảm chiều, nên chỉ mỗi chỉ số bắt đầu là rủi ro. | `apps/api/quality/geometry.py:67` | Hoặc nới thành "điểm đầu là đỉnh có `y` nhỏ nhất (hoà thì `x` nhỏ nhất)", hoặc ghi rõ hạn chế này vào docstring để prompt FE sau biết. Ảnh hưởng thực tế nhỏ: FE dựng góc từ khung gần trục. |
| 3 | P3 | RES-04 | `await storage.delete(new_key)` nằm trong `finally`: kho lỗi đúng lúc đó sẽ **thay** lỗi thật (409/422) bằng lỗi kho và để lại object mồ côi. | `apps/api/quality/service.py:301` | Bọc riêng lời `delete` và chỉ log khi nó hỏng (không `except Exception` — bắt đúng lớp lỗi của `packages.storage`). Dữ liệu tự lành: lịch dọn object mồ côi dưới `uploads/*` quá 24 giờ của B2-04 đã phủ. |
| 4 | P3 | MNT-05 | Nhánh ≈ 1.197 dòng logic (> 400). Giống hệt tình huống đã chấp nhận ở `NO-123` (B2-05a) và `NO-216` (B2-04): khối [10] định nghĩa **một** đơn vị bàn giao (9 module + model + revision + `cases.toml` + test), tách ra sẽ phá thứ tự phụ thuộc B2-04/B5-06a. | `apps/api/quality/**` | Chấp nhận theo tiền lệ; điều phối viên ghi một dòng `DEBT.md` `NO-<nnn>` cùng khuôn `NO-123`/`NO-216` để sổ nợ không đứt mạch. |
| 5 | Nit | TEST-05 | `await asyncio.sleep(1.0)` cố định để chờ ba lời gọi hết hạn 0,3 s — phụ thuộc đồng hồ thật, có thể lung lay trên máy tải nặng. Bản ở tầng route (`test_queue.py:99`) đã làm đúng bằng `asyncio.wait`/`FIRST_COMPLETED`. | `apps/api/quality/tests/test_processing.py:189` | Đổi sang cùng khuôn `asyncio.wait` như `test_queue.py`. |
| 6 | Nit | MNT-02 | Test đọc thành viên riêng tư `processing._pool(3)._max_workers`. | `apps/api/quality/tests/test_processing.py:224` | Khẳng định gián tiếp qua số luồng `quality-imaging` quan sát được (cách `_saturate` đã dùng). |
| 7 | Nit | TEST-01 | [7] nêu riêng "tầng của dự án khác qua đường dự án mình → 404 `floor`" nhưng không có test mang đúng tình huống đó; C08 đi qua **cùng một nhánh mã** bằng `level_id` không tồn tại, và `get_floor` lọc `project_id` (`apps/api/floors/lookup.py:102-104`) nên hành vi đúng theo cấu trúc. | `apps/api/quality/tests/test_routes_{read,corners,straighten}.py` | Thêm một `assert` vào C08 sẵn có: `level_id` của tầng thuộc dự án khác → 404 `floor`. |

Không có finding P0, P1 hay P2.

## Nợ nên ghi (ngoài finding)

- `NO-<nnn>` cho MNT-05 của nhánh này (finding 4), khuôn `NO-123`/`NO-216`.
- `_read_capped` (`service.py:204`) là bản thứ **năm** của cùng một mẫu "gom `open_read` thành bytes có trần" trong repo (`apps/api/drawings/complete.py:136,164`, `apps/ml/runtime/loader.py:202`, `apps/ml/runtime/tasks_util.py:112`). B2-05b **không được** sửa `packages/**` ([12]) nên viết lại tại chỗ là đúng luật ở đây, nhưng đáng một dòng nợ R-07 cấp repo: đưa `read_all_capped(storage, key, *, max_bytes)` vào `packages/storage` rồi năm chỗ gọi lại.
- Nợ tác giả đã nêu (B5-06a phải gọi `save_assessment(run_id=…)` sau `upsert_drawing` cùng giao dịch và dùng lại `corners`/`homography` khi chạy lại) là **việc của prompt sau**, không phải nợ của nhánh này — không cần dòng `DEBT.md`.

## Lệch khỏi prompt — đã xét, chấp nhận hết

Năm mục tác giả khai đều có lý do đứng được và không mục nào thành finding: chữ ký thật theo đính chính K (thắng prompt); `_read_capped` tự viết vì không có helper chung (xem nợ trên); revision viết tay theo đúng khuôn bản sinh của B3-02 (đã kiểm như bản sinh: `lint_migrations` + `migrate_check` đều đạt, 1 head); helper test đặt trong `apps/api/quality/tests/` vì [12] cấm chạm `packages/**`; thông điệp commit theo `CLAUDE.md` thay cho câu mẫu ở [11].5 — đúng, `CLAUDE.md` nói rõ phải viết lại theo mẫu này.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 4 | 0,60 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 4 | 0,40 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 4 | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 | 0,12 |
| **Tổng** | **100%** | | **4,65 / 5** |

## PHÁN QUYẾT: APPROVE

Không P0, không P1, không P2; điểm 4,65 ≥ 4,0 → `APPROVE` theo ma trận `RULE.md` §5.

Nhánh làm đúng phần khó nhất của prompt và làm bằng bằng chứng chứ không bằng lời: nhả kết nối DB trước khi xử lý ảnh **có test pool một kết nối chứng minh**, hàng xử lý 503-trước-khi-gửi-việc **có test hai vòng sự kiện**, đua hai #31 **có test object bên thua bị xoá và đúng một lượt mới**, rollback giao dịch cuối **có test hàng Redis thật rỗng**. Thứ tự khoá theo BE-00 §7 đúng tới cả trường hợp chèn dòng `quality_assessments` mới sau `touch_project`. Độ phủ `apps/api/quality` 100% dòng và 100% nhánh, và đó là độ phủ của test đi qua Postgres/Redis/MinIO thật, không phải của mock. Bảy finding còn lại đều là P3/Nit: hai chốt chặn phòng thủ còn thiếu, một chỗ `finally` có thể che lỗi, một edge hình học mà FE hiện không chạm tới, và ba việc dọn dẹp trong test.

Bốn P3 và ba Nit **không chặn merge**; chúng nên vào một FIX gộp sau, hoặc đi kèm prompt kế tiếp chạm `apps/api/quality`. Điều kiện duy nhất kèm theo là hành chính, không phải kỹ thuật: điều phối viên ghi dòng `DEBT.md` cho MNT-05 (finding 4) theo tiền lệ `NO-123`/`NO-216`.

Merge thuộc phiên gọi review này — phiên review không tự merge.
