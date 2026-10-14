# Review merge fix/qa04-dimensions → main

- Ngày: 2026-10-14 · Reviewer: phiên /merge-review · Commit đầu nhánh: d860c2508c73
- Cổng: phạm vi đầy đủ — lượt 1 của nhánh (R-33b điều kiện 1; diff còn chạm `docs/contracts/**`, thêm file test `.py`, đổi hình dạng dây #35); `bash tools/verify/run.sh verify` mã thoát 1 — bước 3 `mypy --strict` hỏng; 5b, 6, 7, 8 chưa chạy (log: `F:/worktrees/AppBack/_logs/review-qa04-dim-verify.log`)
- Độ phủ: tổng dòng 99,47% · nhánh 98,01% (bước 5 đạt; `apps/api/spatial_write` 100% · 100%; tập file bị chạm 100% · 100%)

## Phạm vi

4 commit, 7 tệp, +226/−7: `spatial_write/{schemas,router,writer}.py` (#35 nhận `body.dimensions`: có → thay nguyên
danh sách, `[]` xoá hết, vắng → giữ nguyên; người gửi kiểm A5 rồi `levelId`), test mới `test_routes_dimensions.py` (4 test),
`test_writer.py` (luật "AI chưa duyệt" chuyển sang người ghi pipeline), `changes/QA-04.md`, `docs/contracts/openapi.json`.
Cây làm việc sạch. Không có pragma, `noqa`, `type: ignore`, skip/xfail mới, không hạ ngưỡng.
`d860c250` (`openapi.json`) do người điều phối commit bằng `run.sh openapi`: chấp nhận theo tiền lệ
`2026-10-13-refactor-f-15-pascal-flag.md:12`. FE (`AppFront` `qa/phase04-run`, `src/api/schemas/spatialLayer.ts:107,124`)
khớp hình dạng BE mới (`dimensions?`, refine ≥ 1 khoá).

## Điều kiện dừng sớm (skill §2) — CHẠM

Trailer `Prompt:` đọc bằng `git log --format='%h [%(trailers:key=Prompt,valueonly)]' main..HEAD`:

| commit | `Prompt` đọc được | lỗi |
|---|---|---|
| `4f5e17f8` feat(spatial-write) | `qa04-dimensions` | mã prompt sai: tệp bàn giao là `changes/QA-04.md` |
| `12e0306e` style(spatial-write) | (rỗng) | không có trailer `Prompt:` |
| `09be4ecc` fix(spatial-write) | `QA-04` | đạt |
| `d860c250` docs(contracts) | (rỗng) | R-36b: dòng trống giữa `Bug: BUG-577` và `Co-Authored-By:` làm khối trailer vỡ |

Thiếu trailer `Prompt:` → REJECT theo skill §2. Review vẫn đi hết các miền để một vòng sửa xử lý đủ.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 0 | P1 | R-33 / TEST | Cổng đỏ: bước 3 `mypy --strict` — `test_routes_dimensions.py:17: Argument 1 to "review" has incompatible type "**dict[str, object]"; expected "str"` và `… expected "bool"` [arg-type] (2 lỗi). Bước 5b, 6, 7, 8 chưa chạy. Báo cáo "đã lint" của tác giả không gồm mypy. | `apps/api/spatial_write/tests/test_routes_dimensions.py:17` | Gọi `review(source=…, reviewed=…)` với tham số có kiểu (vd `_dimension(level_id, source: str = "human", reviewed: bool = True)`), không bung `dict[str, object]`; chạy lại cổng tới bước 8. |
| 1 | P1 | CON-01 / W20 | Lượt ghi `dimensions` của **người** không để lại dòng `floor_change_log` nào: `_write_log` chỉ ghi `diff_layers(old,new)` (chỉ lớp) + dòng `reference_ids` của mục bị gỡ id (`changes += … for item in touched`). `remote_changes_since` (`changes.py:52-54`) chỉ đọc nhật ký này. Hệ quả: A lưu duyệt kích thước (rev 1, 0 dòng log); B cầm `baseVersion: 0` gửi `dimensions` → `remote` rỗng → `_settle_base` đi tiếp, **ghi đè im lặng** việc duyệt của A, không 409. Trái HOP-DONG-MOI §1.3 (Dimension `M-…`: `value_mm`, `override_value_mm`, `reference_ids`; xoá = `__deleted__`, mới = mỗi trường một dòng) và §1.1 (#35 luôn `remoteChanges ≥ 1`). Chính `_touch_marks` (writer.py:589) tồn tại để chặn đúng cảnh này cho lớp ("người thứ hai … ghi đè việc duyệt"); kích thước chưa có. | `apps/api/spatial_write/writer.py:607-625`, `:220` | Diff kích thước cũ/mới theo `id` (mới, xoá `__deleted__`, đổi `value_mm`/`override_value_mm`/`reference_ids`, đổi dấu duyệt → dấu chạm ở trường đại diện) và đưa vào `changes` của `_write_log`. Thêm test thật: hai người, base cũ, chỉ đổi `dimensions` → 409 có `entityType:"dimension"`; và test đọc `floor_change_log` sau lượt ghi `dimensions`. |
| 2 | P1 | API-01 (hợp đồng) | Đổi dây #35 mà hiến chương chưa đổi: HOP-DONG-MOI §4 ghi `FloorLayerWriteBodySchema` = `{layer?, scaleMillimetresPerPixel?}` **strict**, và N16 `dimensions` "chỉ đọc ở v1". Không có bản HOP-DONG-MOI mới, không có bản ghi quyết định (`docs/decisions.md` chưa tồn tại; `tl-decision` §1: quyết định đổi dây phải thêm "Bản N+1"). Chính BUG-577 (`BUG-LOG-P04.md:657`) ghi "lưu thật dimensions là tính năng, xem de-xuat-tinh-nang.md". CLAUDE.md: prompt lệch hiến chương → theo hiến chương. | `apps/api/spatial_write/schemas.py:66`; `docs/contracts/openapi.json:1343-1388` | Người điều phối ghi QD + HOP-DONG-MOI **Bản 11** (§4 #35 thêm `dimensions?` với ngữ nghĩa thay/`[]` xoá/vắng giữ, A5 + `LAYER_LEVEL_MISMATCH` theo `body.dimensions.<i>`; N16 bỏ "chỉ đọc ở v1"; §1.3 nhật ký kích thước do người ghi), người dùng duyệt câu chữ, commit chỉ tài liệu kèm trailer `Charter-Approved:`. |
| 3 | P2 | LOG-01 | Kích thước người gửi không kiểm trùng `id`: lớp có `duplicateId` → `LAYER_INTEGRITY_BROKEN` (`integrity.py:32-35`), còn `_check_human_dimensions` chỉ kiểm A5 và `levelId`. Hai mục cùng `M-…` được lưu, FE khoá theo `id`. Trước nhánh này chỉ pipeline/N19 (dữ liệu server sinh) ghi kích thước nên chưa lộ. | `apps/api/spatial_write/writer.py:277-284` | Thêm kiểm trùng `id` → 422 (`VALIDATION` hay `LAYER_INTEGRITY_BROKEN`, ghi vào Bản 11) + test đỏ→xanh. Không sửa trong nhánh thì mở dòng `DEBT.md`. |
| 4 | P2 | R-36 / R-36b | Trailer `Prompt:` thiếu/vỡ/sai mã ở 3/4 commit (bảng trên). | `12e0306e`, `d860c250`, `4f5e17f8` | Viết lại lịch sử nhánh để mọi commit có khối trailer liền `Prompt: QA-04` (`Fix:`/`Bug:` sát nhau, không dòng trống bên trong); kiểm `git log --format='%(trailers:key=Prompt,valueonly)' main..HEAD` in `QA-04` cho mọi dòng. |
| 5 | P3 | R-01 | Hàm `_dimension_ids` trong test không có docstring. | `apps/api/spatial_write/tests/test_routes_dimensions.py:60` | Thêm một dòng docstring. |

Đã kiểm, không thành finding: SEC — `dimensions` đi qua `WireRequest` strict + mô hình miền `Dimension` (regex id W4, `Mm` int an toàn, refine `valueMm > 0`), quyền giữ nguyên của #35, thân trần 8 MiB như `layer`; A5 và `levelId` cho người ghi có test đường thật (422 + `field`). LOG — `[]` xoá và vắng giữ có test; thân cả tỉ lệ lẫn `dimensions` đổi hệ tỉ lệ qua `_sent_dimensions`; vân tay C09b đã gồm `dimensions` (`body_sha256`). PERF — không truy vấn mới. Luật pipeline cũ giữ nguyên (`_check_arguments` chỉ áp cho `SYSTEM_PIPELINE`, test `test_writer.py` chuyển đúng người ghi).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 1 | 0,15 |
| LOG | 15% | 3 | 0,45 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 1 | 0,10 |
| TEST | 7% | 1 | 0,07 |
| OBS/OPS | 5% | 5 | 0,25 |
| MNT | 3% | 3 | 0,09 |

Tổng: 3,36 / 5

## PHÁN QUYẾT: REJECT

Chạm điều kiện dừng sớm (thiếu trailer `Prompt:`), cổng thoát 1 (mypy), cộng 2 P1 thiết kế. Để được APPROVE phải:
(0) sửa 2 lỗi mypy ở `test_routes_dimensions.py:17`, cổng đầy đủ thoát 0 qua cả bước 5b–8 (#0); (1) mọi commit của nhánh mang trailer
liền `Prompt: QA-04` (#4); (2) ghi nhật ký `floor_change_log` cho kích thước do người ghi theo HOP-DONG-MOI §1.3 và có test
409 hai người chỉ đổi `dimensions` (#1); (3) người điều phối đưa QD + HOP-DONG-MOI Bản 11 được người dùng duyệt, commit kèm
`Charter-Approved:` (#2); (4) kiểm trùng `id` kích thước hoặc dòng `DEBT.md` (#3); (5) docstring `_dimension_ids` (#5);
rồi xin review lại (lượt 2: đích, trừ khi diff vòng sửa chạm điều kiện đầy đủ của R-33b — viết lại lịch sử/đổi `openapi.json`
thì chạy đầy đủ).
