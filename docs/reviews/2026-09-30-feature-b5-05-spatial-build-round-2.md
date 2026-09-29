# Review merge feature/b5-05-spatial-build → main — lượt 2

- Ngày: 2026-09-30 (giờ máy; `date -u` 2026-09-29T18:00Z) · Reviewer: phiên `/merge-review` lượt 2, độc lập tác giả
  · Sha review: `5d9c94583b122a922171f7149aa31329042017a0` · phán quyết lượt 1:
  `docs/reviews/2026-09-30-feature-b5-05-spatial-build.md` (🔶 REQUEST CHANGES, 4,19/5, sha `aaaf92c`)
- **PHÁN QUYẾT: ✅ APPROVE — 4,87/5.** Không finding `P0`/`P1`/`P2`/`P3` mới; hai `Nit` không chặn merge.
- Phạm vi: chỉ diff vòng sửa `git diff aaaf92c..5d9c945` — **9 file, +170/−34**, hai commit
  (`11fb013` F0, `5d9c945` F1/F3/F4/F5/F7/F8/F9/F10 + test nhánh `deduped.pop()`). Tất cả dưới
  `apps/worker/pipeline_build/` — đúng mục sở hữu B5-05, không chạm file prompt khác, không chạm
  `docs/charter/*`, `openapi.json`, `uv.lock`, `tools/**`, `conftest.py`, `pyproject.toml`, `.importlinter`,
  `DEBT.md`, `changes/B5-05.md`. Cây làm việc sạch.

## Cổng (E.10 — lấy từ mã thoát thật, **không** chạy lại)

`Phạm vi kiểm: đầy đủ` — tác giả chạy cổng 8 bước vì vòng sửa đổi tên test `test_<op>__<case>`
(R-33b điều kiện 5) và sửa `build.py` (đường chạy chính). Reviewer **không** chạy thêm container nào.

Log: `backend/dieu-phoi/chay/B5-05/M/gate.log`, `M/gate.sha` = `5d9c945`; log trong container
`20260929T174640Z-5d9c94583b12.log` → **đúng sha**. Worktree `b5-05-build` đang ở đúng
`5d9c94583b122a922171f7149aa31329042017a0`, `git status --porcelain` rỗng — cây khớp sha review.

|  # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `pytest -n` (cov) → `coverage_gate` | đạt | **7078 passed**, 0 failed, 661,43 s |
| 5b | `pytest -m perf` → `case_gate` | **đạt** | perf 1 test (12,95 s); `case_gate: đạt`, 77 thao tác |
| 6 | `lint_migrations` → `migrate_check` | đạt | 19 revision, 1 head, 10/10 mục `migrate_check` |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | 83/83 bản đồ, 80 mount, H1 1772 mẫu, H5 6 khung SSE |
| 8 | `openapi` | đạt | |

**Mã thoát: `EXIT=0`.** Không bước nào "không áp dụng", không bước nào "chưa chạy".

**Bước 5b, `build_pipeline_layer`:** `case_gate` chỉ in dòng task khi **hỏng** — lượt 1 in nguyên văn
`HỎNG task: build_pipeline_layer: thiếu ['J03']`; lượt này log không còn dòng `HỎNG`/`task` nào và
`case_gate: đạt`. Cộng với `cases.toml` khai `require = ["J03", "J08", "J10"]`, `tools/case_gate.py:495`
tự đòi thêm `J01`, `J06`, và năm hàm tên đúng hậu tố trong `tests/test_tasks.py` (`__J01:103`, `__J06:118`,
`__J10:133`, `__J03:153`, `__J08:286`, **không hàm nào `parametrize`** nên không có hậu tố `[…]`) →
**J01 J03 J06 J08 J10 đủ**. Ba `CẢNH BÁO` còn lại là `files_read_object`, `health_live`, `health_ready`
không có dòng BE-BIND — có từ trước, không thuộc nhánh này.

Độ phủ (`coverage_gate: đạt`): tổng dòng **99,53 %** · nhánh **98,16 %**; `apps/worker/pipeline_build`
dòng **98,75 %** · nhánh **94,02 %** (lượt 1: 98,60/93,26 — tăng); `packages/messaging` **100 %/100 %**;
tập file bị chạm **98,80 %/94,15 %**. Mọi gói bị chạm và tổng đều ≥ 90/90.

## Kiểm từng finding lượt 1

| # | Mức lượt 1 | Trạng thái | Bằng chứng trong diff |
|---|---|---|---|
| F0 | **P1** TEST | **đã sửa** (`11fb013`) | `test_tasks.py:153` còn đúng một hàm `test_build_pipeline_layer__J03`, không `parametrize` → khớp trọn vẹn `^test_(?P<fn>.+)__(?P<case>J\d{2})$` (`tools/case_gate.py:296`). Năm hàm `__J01 __J03 __J06 __J08 __J10` đều đúng hậu tố, không hàm nào có `[…]`. Hai ca con của `[8]` (thiếu `walls.json`; `objects.json` khoá lạ) gộp trong một hàm, hai `run_id` khác nhau nên không lẫn. Ca thứ ba (`run_prefix` lượt khác) đúng là poison, đã thành `NO-290`. |
| F1 | **P2** LOG | **đã sửa** | `build.py:173-176`: sau `_checked`, `_filtered_walls` bắt `thickness_px > 0` và hai đầu tường trùng nhau → `ValueError`. Đúng đề xuất lượt 1. Test `test_build_layer__rejects_degenerate_wall` (`test_build_scale.py:161-194`) ba ca `model_construct` (`thickness_px` 0, âm, `start == end`) đều `pytest.raises(ValueError)`; `WallsResult.model_construct` để không bị pydantic chặn trước. **Đã tự kiểm không phải hồi quy:** `WallPx` (`packages/ml_contracts/artifacts.py:102-115`) đã có `Field(gt=0)` và `_not_a_point`, nên đường sản phẩm không đổi hành vi — chỉ vá lớp phòng thủ mà `[6]` bước 1 đòi. |
| F2 | P3 RES | **thành nợ** `NO-290` (`DEBT.md:311`), chủ B5-06c, kế hoạch `PIPELINE_STEP_TIMEOUT` — không tính lại |
| F3 | P3 LOG | **đã sửa** | `build.py:234-243` `_whole_line` đổi đường tim tường **gốc** `walls_px[wall_index]` px → mm; `build.py:354-358` nhánh `tag == "all"` dùng nó thay `wall.centreline` của tường đã gộp ở 3b. `referenceIds`/`confidence` vẫn lấy từ tường giữ (`wall`) đúng như chỉ dẫn vòng sửa. Test `test_build_layer__whole_wall_line_comes_from_input_wall` (`test_build_dimensions.py:116`) khẳng định hai đầu (500,500)–(5500,500). |
| F4 | P3 TEST | **đã sửa** | `test_e2e_wire.py:136-158`: `_millimetre_values` duyệt đệ quy `layer` **và** `dimensions` sau `to_json` seed 100, bắt mọi khoá `…Mm`/`x`/`y`; có `assert values` chống rỗng (bài test không tự vô nghĩa) và loại `bool` khỏi `int`. |
| F5 | P3 TEST | **đã sửa** | `test_tasks.py:286-304`: một hàm `__J08`, không `parametrize`, chạy cả hai payload độc của `[8]` (`schema_version` 2 và `fallback_mm_per_px: "0"`), mỗi ca `caplog.clear()` + khẳng định có bản ghi `poison_message`, `_results(...) == []`, và cuối cùng `broker.llen("pipeline.cpu") == 0`. |
| F6 | P3 MNT | **thành nợ** `NO-291` (`DEBT.md:312`) — không tính lại |
| F7 | P3 API | **đã sửa** | `build.py:75-76` `_SCALE_SOURCES`; `build.py:119-120` `from_json` ném `ValueError` khi `scaleSource` lạ, đặt trước `model_validate` nên B5-06b không đọc lọt. Test `test_built_layer__from_json_rejects_unknown_scale_source` (`test_built_layer.py:87`) với `"banana"`. |
| F8 | P4 MNT | **đã sửa** | `geometry.py:3-7` ghi "một `STRtree` **mỗi pha**" và nêu bốn pha + lý do 3b sửa hình học tại chỗ — khớp mã. |
| F9 | P4 MNT | **đã sửa** | `tasks.py:99-116`: `PIPELINE_ARTIFACT_MAX_BYTES` đọc một lần ở `_build_and_write` rồi truyền xuống `_read_inputs`; chỗ đọc thứ hai đã bỏ. |
| F10 | P4 LOG | **đã sửa** | `build.py:401-410`: `_assembled` chỉ còn bước 3-6; `_attempt` chạy bước 7 rồi mới `apply_post_rules` rồi `check_integrity`, đúng thứ tự khối `[6]`; docstring ghi rõ `Dimension.confidence` là tin cậy tường lúc bước 7. |
| (nợ #4 lượt 1) | — | **đã sửa** | `test_rooms.py:297-308` dựng tay đa giác có điểm cuối `(0.4, 0.4)` `js_round` về `(0,0)` → nhánh `deduped.pop()` (`rooms.py:45-47`) có ca riêng. Không cần dòng `DEBT.md`. |

## Đã tự kiểm (không tin báo cáo tác giả)

1. **F10 là đổi trật tự *trơ*, không đổi byte đầu ra.** `_build_dimensions` đọc `wall_set.walls` và `context`,
   không bao giờ đọc `layer`; `apply_post_rules` là hàm thuần trả lớp mới, mà `Wall` là model đông cứng nên
   `wall_set.walls` không bị sửa tại chỗ. Ở **cả hai** trật tự, `Dimension.confidence` vẫn là tin cậy tường
   **trước** luật 2. `dropped` không bị `apply_post_rules` chạm. Khác biệt duy nhất: khi lớp có lỗi toàn vẹn
   critical thì nay dựng kích thước xong mới ném — cùng một `ValueError`, chỉ phí công trên đường lỗi.
   Vì vậy không có test nào pin được trật tự này, và **không** ghi finding "thiếu test": trật tự mới là điều
   `[6]` viết, docstring nói đúng điều mã làm.
2. **Không hồi quy do F1.** Xem cột bằng chứng F1: `WallPx` đã chặn cả hai điều kiện ở tầng pydantic, nên tường
   suy biến không tới được từ artifact ML thật; một tường xấu **không** làm hỏng cả lượt chạy trong đường sản phẩm.
3. **`_outline_points` test đúng nhánh.** `shapely.Polygon([(0,0),(1000,0),(1000,1000),(0.4,0.4)])`:
   `exterior.coords[:-1]` cho 4 đỉnh, `js_round(0.4) == 0` nên đỉnh cuối thành `(0,0)` — khác đỉnh liền trước
   nên qua được vòng khử trùng liên tiếp, rồi mới rơi vào `deduped[0] == deduped[-1] → pop()`. Đúng nhánh mà
   lượt 1 ghi là chưa phủ.
4. **Ranh giới sở hữu (R-27):** 9 file đổi, tất cả dưới `apps/worker/pipeline_build/` — mục sở hữu của B5-05.
   Không chạm `docs/charter/*`, `openapi.json`, `uv.lock`, `tools/**`, `conftest.py`, `pyproject.toml`,
   `.importlinter`, `DEBT.md`, `changes/B5-05.md`. Cây làm việc sạch (`git status --porcelain` rỗng).
5. **K24 sạch:** không `# pragma: no cover`, `pragma: no branch`, `skip`, `xfail`, `# noqa` trần hay
   `# type: ignore` không mã nào mới trong diff (grep toàn `apps/worker/pipeline_build/` không ra).
6. **Commit:** hai commit, dòng đầu đúng Conventional Commits ≤ 72 ký tự
   (`test(pipeline-build): name the J03 task case exactly`,
   `fix(pipeline-build): address merge review round one`), thân có trailer `Prompt: B5-05`.
7. **Mọi định danh mới trong test đều giải được:** `_some_id`, `OUTBOX`, `LEVEL_ID`, `SIZE`, `_run`, `_texts`,
   `ObjectsResult`, `TextResult`, `WallsResult`, `json`, `Any`, `shapely`, `_outline_points` — đã tra từng cái.

## Finding mới

| # | Mức | ID | Vị trí | Vấn đề | Đề xuất |
|---|---|---|---|---|---|
| G1 | Nit | MNT-02 | `apps/worker/pipeline_build/build.py:173`, `:175` | `raw.size and …` là điều kiện thừa: với mảng rỗng `(0, 6)`, `(raw[:, 4] > 0.0).all()` đã là `True` và `…any()` đã là `False`. Hai vế `and` không bao giờ đổi kết quả. | Bỏ `raw.size and`, hoặc gộp hai phép kiểm vào `_checked` cho cùng chỗ với NaN/`confidence` (docstring `_checked` mới là chỗ khẳng định "không tin `model_construct`"). |
| G2 | Nit | MNT-02 | `apps/worker/pipeline_build/build.py:130-134` | Docstring `_checked` vẫn tự nhận là chốt "không tin ràng buộc của B5-01 (bước 1)" trong khi hai bất biến bước 1 mới (`thickness_px > 0`, hai đầu khác nhau) nằm ở hàm gọi. Người đọc sau dễ thêm nhầm chỗ. | Một câu trong docstring `_checked` trỏ sang `_filtered_walls`, hoặc dời hai phép kiểm vào `_checked` như G1. |

Không finding `P0`/`P1`/`P2`/`P3` mới. Hai Nit trên **không** chặn merge và **không** cần dòng `DEBT.md`.

## Nợ nên ghi

Không có nợ mới. Ba dòng `NO-290`, `NO-291`, `NO-292` đã có trong `DEBT.md` và phủ đúng F2, F6 và mục `[11].5`;
cả ba đều `P3`, có chủ, không chặn merge theo R-35/R-38. Nợ số 5 của lượt 1 (`audit.py` chạy Python 3.11 của máy,
lỗi cú pháp PEP 695) là nợ công cụ điều phối, không thuộc nhánh này.

## Điểm

| Miền | Trọng số | Điểm | × |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (F1, F3, F10 đã sửa) | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 4 (F2 còn nợ `NO-290`, chủ B5-06c) | 0,40 |
| DB, API – Migration & contract | 10 % | 5 (F7 đã sửa) | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (F0, F4, F5 + nhánh `deduped.pop()`) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 (F6 còn nợ `NO-291`; hai `Nit` G1, G2) | 0,12 |
| **Tổng** | **100 %** | | **4,87 / 5** |

## PHÁN QUYẾT: ✅ APPROVE

Cả mười finding của lượt 1 đã được xử lý đúng: tám cái sửa trong mã kèm test mới, hai cái (F2, F6) chuyển
thành nợ `NO-290`, `NO-291` có chủ và có kế hoạch — cộng thêm `NO-292` cho `step_done` chờ B5-06c, đều `P3`,
không cái nào chặn merge theo R-35/R-38. Finding `P1` chặn merge của lượt 1 (tên test `__J03` trượt
`case_gate`) đã hết: bước 5b nay `đạt` và các bước 6, 7, 8 — chưa từng chạy ở nhánh này — đều xanh trong
cùng một lượt cổng đầy đủ, `EXIT=0`. Vòng sửa không thêm lỗi mới, không rò ra ngoài mục sở hữu, không
`pragma`/`skip`/`xfail`/hạ ngưỡng, và độ phủ của `apps/worker/pipeline_build` còn nhích lên (98,75/94,02).
Hai `Nit` (G1 điều kiện `raw.size and …` thừa, G2 docstring `_checked` lệch chỗ) là gu bảo trì, tác giả tự
quyết, không cần dòng `DEBT.md` và **không** phải điều kiện để merge.

Điểm 4,87/5, không `P0`/`P1` → **APPROVE**. Nhánh được vào `main` (việc merge thuộc phiên gọi, không phải
phiên review này).
