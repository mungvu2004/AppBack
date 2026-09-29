# Review merge feature/b5-05-spatial-build → main

- Ngày: 2026-09-30 (giờ máy; `date -u` 2026-09-29T17:31Z) · Reviewer: phiên `/merge-review` lượt 1, độc lập tác giả
  · Sha review: `aaaf92c77057c67c273a71fcb6fb78109e214524` · cây `246027b6f1615a8547600877fc1f3174b283ac05`
- **PHÁN QUYẾT: 🔶 REQUEST CHANGES — 4.19/5** (một finding **P1**: cổng lớp gộp đỏ ở đúng sha này).
- Phạm vi: `git diff main...aaaf92c` — 30 file, +3739/−0, đúng ba mục sở hữu của `[10]`:
  `apps/worker/pipeline_build/**` (10 module + `cases.toml` + 17 file test), `packages/messaging/payloads/pipeline.py`,
  `changes/B5-05.md`. Không chạm file của prompt khác, không chạm `docs/charter/*`, `tools/**`, `conftest.py`,
  `pyproject.toml`, `uv.lock`, `.importlinter` (`[12]` sạch).

## Cổng (E.10 — lấy từ mã thoát thật, **không** chạy lại)

Log: `backend/dieu-phoi/chay/B5-05/M/gate.log` (`M/gate.sha` = `aaaf92c`); log trong container
`20260929T171753Z-aaaf92c77057.log` → **đúng sha**; worktree `b5-05-build` đang ở đúng `aaaf92c`, `git status` sạch.

|  # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | |
| 1 | `ruff format --check` | đạt | 1115 file |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | 930 file |
| 4 | `lint-imports` | đạt | 10 hợp đồng giữ, 0 vỡ |
| 5 | `pytest -n` (cov) → `coverage_gate` | đạt | **7072 passed**, 0 failed, 710,78 s |
| 5b | `pytest -m perf` → `case_gate` | **hỏng** | perf 1 test đạt (13,92 s); `case_gate: hỏng` |
| 6 | `lint_migrations` → `migrate_check` | chưa chạy | |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | chưa chạy | |
| 8 | `openapi` | chưa chạy | |

**Mã thoát: 1.** Không bước nào "không áp dụng".

Độ phủ (`coverage_gate: đạt`): tổng dòng **99,52 %** · nhánh **98,16 %**; `apps/worker/pipeline_build`
dòng **98,60 %** · nhánh **93,26 %**; `packages/messaging` **100 %/100 %**; tập file bị chạm 98,66 %/93,41 %.
Không `# pragma: no cover`, không `skip`, không `xfail`, không hạ ngưỡng (K24 sạch). Bốn `# noqa`/`# type: ignore`
đều có mã và lý do bằng lời.

## Finding chặn merge

**F0 · P1 · TEST · `apps/worker/pipeline_build/tests/test_tasks.py:152` và `:161`**

`case_gate` báo `HỎNG task: build_pipeline_layer: thiếu ['J03']`, làm bước 5b hỏng và bước 6–8 không chạy.
Nguyên nhân: `tools/case_gate.py:296` khớp tên test task bằng `^test_(?P<fn>.+)__(?P<case>J\d{2})$` — **neo
cuối chuỗi**. Hai test J03 tên `test_build_pipeline_layer__J03_missing_artifact` và
`…__J03_invalid_artifact` nên không khớp, `J03` không bao giờ được ghi nhận, dù `cases.toml` khai
`require = ["J03", "J08", "J10"]` và nội dung hai test **đúng** yêu cầu `[8]`. `J01`, `J06`, `J08`, `J10` khớp bình thường.

Đề xuất: gộp thành **một** hàm tên đúng `test_build_pipeline_layer__J03` chạy cả ba ca con của `[8]` (thiếu
`walls.json`; `objects.json` khoá lạ/quá trần; `run_prefix` của lượt khác). Không dùng `parametrize` cho hàm
này — tên nút junit sẽ mang hậu tố `[…]` và vẫn trượt cùng biểu thức chính quy.

## Finding còn lại

| # | Mức | Miền | Vị trí | Vấn đề | Đề xuất |
|---|---|---|---|---|---|
| F1 | **P2** | LOG | `apps/worker/pipeline_build/build.py:218` (và `:126-137`) | `[6]` bước 1 bắt "không tin đầu vào (kể cả `model_construct`)" và docstring `_checked` khẳng định đúng câu đó, nhưng `_checked` chỉ kiểm hữu hạn + `confidence ∈ [0,1]`. `WallPx.model_construct(thickness_px=0.0)` lọt tới `_build_scale`, ở đó `150.0 / median` ném **`ZeroDivisionError`** — không phải `ValueError` — nên `tasks._build_and_write` (`except ValueError`) không đổi được thành `PIPELINE_BUILD_INVALID`; thông điệp rơi vào đường thử lại/DLQ thay vì `step_done failed`. Đường sản phẩm không tới được (`walls_from_json` có `Field(gt=0)`), nên đây là thủng lớp phòng thủ prompt đòi, không phải lỗi chạy thật. | Thêm `thickness_px > 0` (và `start != end`) vào `_checked`/`_filtered_walls`, hoặc chắn `median <= 0 → return final`. |
| F2 | P3 | RES | `tasks.py:272-278`, `packages/messaging/payloads/pipeline.py:48-55`, `tests/test_tasks.py:194` | `[8]` J03 đòi "`run_prefix` của lượt khác → `…_INVALID`" (tức `step_done failed`). Vì `BuildStepPayload` đã tự kiểm `run_prefix` (cũng do `[2]` đòi), thông điệp loại này thành **poison** ở lớp giải — không có `step_done` nào. `_check_run_prefix` chỉ còn kích được bằng `model_construct`. Prompt tự mâu thuẫn; mã theo hiến chương (BE-00 §7 poison) là đúng, nhưng hệ quả "B5-06c không bao giờ biết bước hỏng" chưa ai ghi nợ. | Ghi nợ cho B5-06c: bước không báo `step_done` phải có hạn chờ. Không cần sửa B5-05. |
| F3 | P3 | LOG | `build.py:336` | Với `tag == "all"`, `line` lấy `wall.centreline` của tường **đã gộp ở 3b**, còn `valueMm` là `real_length_mm` đo trên tường gốc trước khi gộp. Tường bị khoét hai khe cửa rồi gộp lại dài hơn hẳn tường gốc, nên `line` và `valueMm` lệch xa hơn ngưỡng 2 % mà phần còn lại bước 7 giữ. | Dùng `context.walls_px[wall_index]` cho cả nhánh `"all"`, hoặc bỏ mẫu khi `len(seg.inputs) > 1`. |
| F4 | P3 | TEST | `tests/test_e2e_wire.py:52` | `[6]` liệt kê "mọi mm là `int`" trong "Bất biến (**có test**)"; không test nào khẳng định. Bất biến vẫn đúng về cấu trúc (`Mm = SafeInt`, `packages/domain/spatial/model.py:79`) nhưng đó là B3-01 giữ hộ. | Một vòng qua `dump` khẳng định mọi khoá `…Mm`/`x`/`y` là `int`. |
| F5 | P3 | TEST | `tests/test_tasks.py:284` | J08 của `[8]` có hai payload độc (`schema_version` 2 **và** `fallback_mm_per_px: "0"`) và đòi log `poison_message`. Test chỉ chạy ca `schema_version` 2, không khẳng định log. | `parametrize` hai payload + `caplog`. |
| F6 | P3 | MNT | `tests/test_e2e_wire.py:27`, `test_e2e_real.py:44`, `test_scale_seeds.py:49`, `test_build_scale.py:34`, `test_build_dimensions.py:42` (+ hai chỗ nội tuyến ở `test_perf.py:97`) | R-07: năm bản sao gần giống nhau của cùng vỏ bọc `render_plan(seed) → build_layer(level_id=…, walls=WallsResult(...), …)`, kèm `_FALLBACK_MM_PER_PX = Decimal("10")` và `_LEVEL_ID` khai lại ở 5 file. CLAUDE.md đã chỉ chỗ để chung. | `build_from_plan(...)` trong `packages/testing/factories/pipeline_build.py`. |
| F7 | P3 | API | `build.py:121` | `from_json` kiểm bộ khoá gốc và bộ khoá `dropped` nhưng gán thẳng `scale_source=payload["scaleSource"]`: `layer.json` có `"scaleSource": "banana"` đọc lọt thành `BuiltLayer` phá `Literal` đã khai — B5-06b đọc file này bằng `from_json`. | Kiểm `in ("pipeline", "project_default")` → `ValueError`. |
| F8 | P4 | MNT | `geometry.py:3-5` | Docstring module viết "một `STRtree`" trong khi module dựng bốn cây (lý do đúng, câu chữ lệch mã). | Sửa thành "một cây mỗi pha". |
| F9 | P4 | MNT | `tasks.py:300` và `:329` | `get_pipeline_build_settings().PIPELINE_ARTIFACT_MAX_BYTES` đọc hai lần trong cùng lượt task. | Đọc một lần, truyền xuống. |
| F10 | P4 | LOG | `build.py:386-389` | Bước 7 chạy **sau** `apply_post_rules` (bước 8), nên `Dimension.confidence = min(chữ, tường)` lấy `confidence` tường **trước** luật 2; luật 2 có thể hạ nó bằng `min` (`packages/domain/rules_ai/post_rules.py:187-196`). Hình học không đổi (luật 2 chỉ đổi `kind`/tin cậy) nên `line`/`referenceIds` vẫn đúng. | Dựng `Dimension` từ `layer.walls` sau luật, hoặc ghi rõ là cố ý. |

## Đã tự kiểm (không tin báo cáo tác giả)

1. **Lệch #3 — `wall_spans` trên tập con là đúng, không phải xấp xỉ.** `_SpanIndex.spans`
   (`build.py:309-316`) tra `dwithin` với `distance = max(t_j/2, max(mọi t)/2)` = `max(mọi t)/2`.
   `_WallIndex.spans` (`packages/vision/dimensions/pairing.py:57-79`) chỉ nhận đóng góp của tường `k` khi
   (a) hai tim cắt nhau thật (`proper`, khoảng cách hình học = 0) hoặc (b) một đầu của `k` cách **đoạn** `j`
   không quá `max(t_j, t_k)/2`. Cả hai đều kéo theo khoảng cách tối thiểu giữa hai `LineString` ≤ `max(mọi t)/2`,
   nên tập con là **bao trùm**. Chiều ngược: mọi đại lượng trong `spans(j)` tính theo từng phần tử (`vec/length`,
   `np.hypot`) — không có phép thu gọn nào qua các tường — nên tường thừa trong tập con cho `proper = False`
   và `gap > reach`, không sinh điểm chia; `_merge_points` lại sắp xếp nên không phụ thuộc thứ tự. Kết quả
   **trùng từng bit**. `test_span_index__matches_wall_spans_on_seed_100` (`test_build_dimensions.py:108`)
   khẳng định đúng điều này trên seed 100. **Chấp nhận**, không dựng được phản ví dụ.
2. **Lệch #1 — `cases.toml` thêm J10:** `docs/charter/CASE.md:131` ghi nguyên văn "task `pipeline.*` bắt buộc
   thêm J10", còn `tools/case_gate.py:495` chỉ tự đòi `{"J01", "J06"}`. Khai thêm là **đúng hiến chương**. Chấp nhận.
3. **Lệch #2 — id mẫu `sall`:** `pairing.py:121` sinh `("sall", length)`; prompt ghi `all`. `_SAMPLE_ID`
   (`build.py:65`) khớp `s(\d+|all)` và `_build_dimensions` so `tag == "all"` — đúng tên thật. Chấp nhận (xem F3).
4. **Lệch #4 — bốn `STRtree`, tim tường lúc vào 3b, ba hằng cục bộ:** 3b sửa hình học tại chỗ (`_absorb`,
   `_extend_once`) nên cây của pha trước hết đúng; mỗi pha vẫn là **một** truy vấn theo lô, không vòng O(n²).
   `_Centrelines` tra trên tập lúc vào là đúng vì tường gộp là hợp của các tường vào **trên cùng đường thẳng**
   và `crosses` đã bỏ qua mọi `inputs` đã gộp (`geometry.py:140-144`). `_ALIGN_SIN` là 2° của prompt;
   `_PERPENDICULAR_COS` lấy cùng 2° (prompt không nêu số) — hợp lý; `_MIN_DOUBLE_DOOR_MM = 600` là số trong `[6]`
   bước 4. Chấp nhận, trừ câu docstring ở F8.
5. **Lệch #5 — `STRtree.query(..., predicate="within")`:** ngữ nghĩa shapely 2.x là
   `predicate(input_geometry, tree_geometry)`, nên "điểm `within` đa giác" đúng chiều; `"contains"` sẽ luôn rỗng.
   `min(candidates)` cho "phòng đầu tiên" theo thứ tự `rooms` như `[6]` bước 6. Chấp nhận.
6. **`schema_version: int = 1` thay `Literal[1]` của `[2]`:** `packages/messaging/tasks.py:63` bắt lớp con khai
   đúng `schema_version: int = <n>`, và `_schema_version_of` (`:177-184`) đọc mặc định để lọc poison. Mã theo
   hiến chương; J08 vẫn là poison. Chấp nhận, không tính finding.
7. **Trình tự bước 1→8, hàm thuần, K19/K20:** `build_layer` lọc trần/NaN/`confidence`/`outOfImage` trước, rồi tỉ lệ,
   rồi 3→6, `apply_post_rules`, `check_integrity`; `s_dựng` không ghi ra, `scale_source` không đổi;
   `rescale_unreviewed`/`rescale_dimensions` chỉ chạy khi `build != final`, `RescaleError` dựng lại ở `s` với
   `dropped` **đặt lại từ `base`** (không cộng dồn hai lượt) và chỉ log, không ném. Không `round()` dựng sẵn ở đâu
   (chỉ `js_round`); không mặc định 1 mm/px — `_resolved_scale` chỉ có hai nguồn `infer_scale` và `fallback`.
   Không `except Exception`, không nhập `packages.db`/`sqlalchemy`/`apps.api`/`apps.ml`/`torch`/`onnxruntime`
   (bước 4 của cổng xác nhận). `dropped` đủ 12 khoá, thứ tự `DROPPED_KEYS`. Không khai task `pipeline.orchestrate.*`.
8. **Ma trận `[8]`:** 105 test trên 17 file; mọi dòng "Test đặt tên theo việc" đều có test tương ứng (id, tỉ lệ,
   tường, ô mở, phòng, đồ, kích thước, luật hậu xử lý, dây 40 seed, dây thật 10 seed, fuzz 200 bộ, tất định,
   hiệu năng `@pytest.mark.perf` in bằng `logging`, ranh giới tiến trình con **không** `skip`). Thiếu đúng hai
   mục: bất biến "mọi mm là `int`" (F4) và nửa sau của J08 (F5).

## Nợ nên ghi (`DEBT.md`, người điều phối)

1. `NO-` F1: `_build_scale` chia cho 0 khi bề dày trung vị bằng 0 với đầu vào `model_construct` (P2, phải có
   ticket trước khi merge theo RULE §5).
2. `NO-` F2: B5-06c cần hạn chờ cho bước không bao giờ báo `step_done` (thông điệp `run_prefix` sai thành poison).
3. `NO-` F6: gộp vỏ bọc `build_layer` của 5 file test vào `packages/testing/factories/pipeline_build.py`.
4. `NO-` (B đã nêu): `rooms.py:45-47` nhánh `deduped.pop()` (điểm khép trùng sau `js_round`) chưa có ca dựng tay riêng.
5. `NO-` (C đã nêu): `~/.claude/skills/orca-coordinator/scripts/audit.py` chạy bằng Python 3.11 của máy nên
   `SyntaxError` với cú pháp generic PEP 695 mà ruff (UP047) bắt buộc.
6. `NO-` (`[11]`.5): task `pipeline.orchestrate.step_done` chưa có chủ, chờ B5-06c.

## Việc phải làm trước lượt 2

1. Đổi tên hai test J03 thành một `test_build_pipeline_layer__J03` (F0) và chạy lại cổng **đầy đủ** — bước 6, 7, 8
   chưa từng chạy ở nhánh này.
2. Sửa F1 hoặc mở ticket cho nó (RULE §5: P2 phải có ticket).
3. F3, F4, F5, F7 nên sửa trong cùng vòng (đều nhỏ, cùng module); F6, F8–F10 tác giả tự quyết.

## Điểm

| Miền | Trọng số | Điểm | × |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 3 (F1 P2) | 0,45 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 4 (F2) | 0,40 |
| DB, API – Migration & contract | 10 % | 4 (F7) | 0,40 |
| TEST – Kiểm thử | 7 % | 1 (**F0 P1**) | 0,07 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 (F6) | 0,12 |
| **Tổng** | **100 %** | | **4,19 / 5** |

Quyết định: 🔶 **REQUEST CHANGES** — có P1 chưa waiver (RULE §5, ma trận quyết định), bất kể tổng điểm.
Nội dung nghiệp vụ của B5-05 rất chắc; cái chặn là một tên test và một lỗ phòng thủ nhỏ.
