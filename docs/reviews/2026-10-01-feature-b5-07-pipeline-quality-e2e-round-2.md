# Review merge feature/b5-07-pipeline-quality-e2e → main — lượt 2

- Ngày: 2026-10-01 · Reviewer: phiên /merge-review (cùng phiên lượt 1) · Commit đầu nhánh: `a12ebd314d9d` (cây `0c5c50391fd1`)
- Lượt 1: `889b603`, **REQUEST CHANGES 4,40/5**, 1 P1 + 3 P2 + 3 P3 + 3 Nit
  (`docs/reviews/2026-10-01-feature-b5-07-pipeline-quality-e2e.md`).
- Phạm vi: `git diff 889b603..a12ebd3` — 5 file, +256/−193. Chỉ soát vòng sửa; phần lượt 1 đã chấp nhận không mở lại
  (vòng sửa không chạm `report.py`, `tasks.py`, `cases.toml`, `changes/B5-07.md`, `test_runtime.py`).
- Hai commit: `30340ff fix(pipeline-quality): address review round 1 findings`,
  `a12ebd3 fix(pipeline-quality): cast unreachable redis-py None branch for mypy` — dòng đầu đúng mẫu, trailer
  `Prompt: B5-07`. Cây sạch. K24 vẫn sạch: không `pragma`, không `skip`/`xfail`, đúng một `# type: ignore[method-assign]`
  có mã và lý do (`test_runtime.py:191`, có từ lượt 1); `cast` mới **không** phải `type: ignore`.
- Phạm vi kiểm: **đầy đủ** — R-33b (5).

## Cổng — bảng E.10 lượt 2 (mã thoát thật, `M/gate-2.log`)

Log đúng sha và cây đang review: `M/gate.sha` = `a12ebd3`, tên log cổng
`…/verify/20261001T105050Z-a12ebd314d9d.log` (`gate-2.log:1`), `git rev-parse a12ebd3^{tree}` = `0c5c50391fd1`.

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | (gồm `cast` mới ở `service.py:74`) |
| 4 | `lint-imports` | đạt | 10 hợp đồng giữ, 0 vỡ |
| 5 | `pytest -n` (cov) → `coverage_gate` | đạt | 7264 passed, 440,60 s |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm; 77 thao tác, 3 cảnh báo (có từ trước: `files_read_object`, `health_live`, `health_ready`) |
| 6 | `lint_migrations` → `migrate_check` | đạt | 20 revision, 10 phép kiểm `migrate_check` đều đạt |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | **H1 1773 mẫu response** (lượt 1: 1772), H1 ngữ cảnh 64 (lượt 1: 63) |
| 8 | `openapi` | đạt | 236965 byte (không đổi — B5-07 không có endpoint) |

**Mã thoát: 0.**

- Độ phủ: tổng dòng **99,50%** · nhánh **98,10%**; `apps/worker/pipeline_quality` dòng **99,40%** · nhánh **96,15%**
  (lượt 1: 98,81 / 92,86 — vòng sửa nâng nhánh +3,29 điểm nhờ bộ bốn tường, test đếm `streams_redis`, và xoá nhánh chết);
  tập file bị chạm 99,40 / 96,15. Cả bốn con số ≥ 90/90.
- **Bước 7 là bằng chứng độc lập cho finding 1:** H1 tăng từ 1772 lên **1773** mẫu và H1 ngữ cảnh từ 63 lên 64, trong khi
  vòng sửa không thêm test nào (7264 passed ở cả hai lượt) và không thêm thao tác nào (`openapi` cùng 236965 byte). Đúng
  **một** mẫu mới vào H1 — mẫu `spatial_read_layer/C01_pipeline` mà lượt 1 chứng minh là thiếu. Không phải chỉ probe cục
  bộ: chính lượt cổng đầy đủ thấy nó.
- `openapi.json` trong repo không cần làm mới: bước 8 ra đúng số byte của lượt 1, B5-07 không thêm route.

## Đóng finding lượt 1

| # lượt 1 | Mức | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | **P1** | **đóng** | `tests/e2e/test_pipeline_e2e.py:63` nhập `ObservedClient`, `:124` dùng nó với `base_url="https://appback.test"`; docstring `:117-120` ghi lại đúng lý do. Tự kiểm bằng `M/pre-2.log:609-612`: cùng lệnh probe của lượt 1, cây mẫu giờ có **hai** tệp — `spatial_read_layer/C01-1.json` (đối chứng B3-02) **và** `spatial_read_layer/C01_pipeline-1.json` (e2e). Mẫu N16 do pipeline sinh giờ thật sự vào H1. Chỉ response N16 được ghi: với mọi lượt khác (#5-#8, #19, N17) `matched.op != parsed[0]` nên `record_response` bỏ qua — không rác mẫu. |
| 2 | P2 | **đóng** | Ba hàm test về dưới trần R-08: `test_spatial_read_layer__C01_pipeline` 131 → **49** dòng (`:380-428`), `test_pipeline_e2e_rerun_keeps_reviewed` 67 → **34** (`:431-464`), `test_pipeline_e2e_rerun_rescales_page` 83 → **48** (`:467-514`). Mọi helper mới cũng ≤ 50 (lớn nhất `_assert_pipeline_layer` 33). |
| 3 | P2 | **đóng** | `_read_doc` còn **một** bản dùng chung ba test (`:342-347`); thêm `_signed_in_scene` (`:173`), `_run_pipeline` (`:214`), `_fetch_layer` (`:235`), `_layer_lists` (`:246`), `_review_first_wall` (`:350`, tuỳ chọn `scale=` gộp cả ca tỉ lệ gắn trang). Ba khối lặp của lượt 1 không còn. **Refactor không mất khẳng định nào**: đã đối chiếu từng assert của ba test với bản `889b603` — `status == "completed"` chuyển vào `_run_pipeline`, `scaleStatus` vào `_fetch_layer`, bộ số đo + `source`/`reviewed` vào `_assert_pipeline_layer`; không assert nào bị bỏ. |
| 4 | P2 | **đóng** | `test_report.py:32-49` dựng đúng bốn tường của [8] (AI 0,5 · AI 0,9 · `human` 0,3 · `human reviewed` 0,2), ngưỡng 0,7 → `walls == 1`. Hai điều kiện loại trừ của `report.py:67` giờ mỗi cái có một tường đi qua **nhánh sai** của nó; tham số `_wall(extra=…)` không còn là mã chết. Docstring nói rõ bỏ điều kiện nào thì tường nào bị đếm nhầm. |
| 5 | P3 | **đóng** | `tests/helpers.py` không còn nhập `apps.ml` (hai dòng `from apps.ml.runtime…` đã bỏ, `reset_infer_context` khỏi `_TASK_RESETS`, `reset_ml_settings_cache` khỏi `caches`). Phần ML về fixture `e2e_env` của `tests/e2e/test_pipeline_e2e.py:92-104` — nơi [9] cấp ngoại lệ — và `e2e_app`/`e2e_worker` đổi sang phụ thuộc `e2e_env`, nên thứ tự "đặt biến môi trường trước, reset cache sau" vẫn đúng. Không lặp lại phần `process_env` → R-07 vẫn giữ. |
| 6 | P3 | **đóng** | Nhánh không tới được `if fields is None` đã xoá (`service.py:69-74`). Thay bằng `cast("dict[str, str]", fields)` kèm comment nêu đúng lý do (stub redis-py rộng hơn giá trị thật) — `cast` không phải `type: ignore`, không có nhánh nào không phủ được nữa. |
| 7 | P3 | **đóng** | `test_service.py:181-205` `monkeypatch` `service.streams_redis` thành hàm đếm-rồi-ném và khẳng định `calls == 0`. Nay bỏ chặn `status == "completed"` ở `_handle_early_exit` thì `AssertionError` lọt ra khỏi `run_quality` (`except (TimeoutError, RedisError)` không bắt nó) → test đỏ. Khẳng định đã thành chịu lực. |
| 8 | Nit | **đóng** | `test_pipeline_e2e.py:455` → `assert any(v["floorRevision"] == revision_after_review for v in version_items), version_items`. |
| 9 | Nit | **chưa** | `tasks._storage()` / `tasks._STORAGE._factory` vẫn bị test chạm (`test_service.py:307`, `test_runtime.py:158`, `:219`). Lượt 1 đã nói "để sau" — xin một dòng `DEBT.md`. |
| 10 | Nit | **đóng cho mã sản phẩm** | `service.py` sạch vết điều phối: "chủ: việc A" bỏ khỏi `run_quality`/`fail_quality`, `(F1)`/`(F2)`/`(F3)` bỏ khỏi `_run_status`, `_handle_early_exit` và comment `FLOOR_DELETED` (thay bằng `[6]`, `K33`, `R-05`). Dư lượng chỉ còn trong docstring **test** — xem finding mới 11. |

## Finding mới của vòng sửa

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 11 | P3 | MNT-04 | Hai docstring test **sai sự thật**, không chỉ là vết điều phối. (a) `test_runtime.py:3` "Chia việc với test lõi (việc A, `test_rules.py`)" — **`test_rules.py` không tồn tại** trong nhánh (thư mục có `helpers.py`, `test_report.py`, `test_runtime.py`, `test_service.py`); người đọc trên `main` sẽ đi tìm một tệp không có. (b) Docstring module `tests/e2e/test_pipeline_e2e.py:5-7` nói "**hai** test ở đây" (thực tế bốn) và giải thích theo nhánh `feature/b5-07-core` cùng một `run_quality` ném `NotImplementedError` — cả hai không còn tồn tại sau khi gộp. | `apps/worker/pipeline_quality/tests/test_runtime.py:3`; `tests/e2e/test_pipeline_e2e.py:5-7` | (a) trỏ `test_service.py` (tệp thật) hoặc bỏ mệnh đề chia việc. (b) viết lại hai câu theo trạng thái sau gộp: bốn test, dây thật chạy tới `qualityCheck`. |
| 12 | Nit | MNT-04 | Vết điều phối còn trong docstring test: `(B)`/`(C)` (`tests/helpers.py:46`), "việc A"/"việc B" (`test_service.py:4`), `(F1)` (`test_service.py:245`), `(C2)` (`tests/e2e/test_pipeline_e2e.py:98`). Vô hại nhưng không tra được từ `main`. | như trên | Thay bằng tên tệp thật hoặc trích `[8]`/`K`-mã; gộp cùng finding 11. |
| 13 | Nit | MNT-01 | `_assert_pipeline_layer` nhận **7 tham số vị trí**, trong đó `start` chỉ dùng cho một dòng log (B5-06a từng có P3 cho "8 đối số vị trí"). | `tests/e2e/test_pipeline_e2e.py:252-254` | Nhận cả `body` (hoặc tuple của `_layer_lists`) thay bốn danh sách rời, và log thời gian ở người gọi thay vì truyền `start` xuống. |

Không có P0, P1, P2 mới. Vòng sửa không làm hỏng phần nào lượt 1 đã chấp nhận: thứ tự [6] bước 1–4, ba pha K36,
K18 (hai test đếm `completed`), K33 (`record_step` là đường ghi duy nhất), `quality.json` đúng [2], `cases.toml` chỉ case J,
không `except Exception` — tất cả nguyên vẹn; `service.py` chỉ đổi một biểu thức `cast` và bốn docstring/comment.

## Số đo thật từ vòng sửa (`M/pre-2.log:294`)

```
e2e C01_pipeline: tường=5 (plan=5) ô mở(door)=2 đồ đạc=6 phòng=2
  scale=10.035092 plan.mm_per_px=10.000000 lệch=0.3509% thời gian=1.2s
```

Khớp từng ngưỡng [6]: tường 5 ≥ 50% của 5; ≥ 1 ô mở `door`, ≥ 1 đồ đạc, ≥ 1 phòng; tỉ lệ lệch 0,35% ≤ 5% ([11].5 đạt).

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 5 | 0,35 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 | 0,12 |
| **Tổng** | **100%** | | **4,97 / 5** |

## PHÁN QUYẾT: APPROVE

Cổng đầy đủ lượt 2 xanh ở đúng sha `a12ebd3` (mã thoát 0, phủ 99,40% dòng / 96,15% nhánh cho gói bị chạm).
Tám finding chặn hoặc nên-sửa của lượt 1 đều đóng, và đóng **đúng gốc** chứ không vá quanh triệu chứng: P1 sửa bằng
`ObservedClient` nên mẫu `spatial_read_layer/C01_pipeline` thật sự vào H1 (tự kiểm trên cây mẫu, không tin báo cáo);
R-07/R-08 sửa bằng một đợt tách helper duy nhất làm cả ba test ngắn lại mà **không mất khẳng định nào** (đã đối chiếu
từng assert với `889b603`); bộ bốn tường của [8] làm hai điều kiện loại trừ của `_low_confidence_count` thành chịu lực;
test "không chạm Redis" giờ đỏ khi mất chặn; nhánh không tới được đã xoá thay vì che. Phần `apps.ml` về đúng nơi [9] cấp
ngoại lệ mà không nhân đôi `process_env`.

Còn lại một P3 và ba Nit, đều là docstring và chữ ký helper trong test — không chạm hành vi, không chặn merge.

**Điều kiện merge:** một dòng `DEBT.md` gộp finding 11, 12, 13 của lượt này cùng finding 9 của lượt 1 (tất cả thuộc chủ
B5-07, `apps/worker/pipeline_quality/tests` + `tests/e2e`), rồi gộp squash vào `main`.
