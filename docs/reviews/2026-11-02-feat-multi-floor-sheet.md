# Review merge feat/multi-floor-sheet → main

- Ngày: 2026-11-02 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 5b4ddccc3022 (trên `origin/main` 2e999b03, sau 1 commit)
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 1, lượt 1). Phiên chính đang chạy `bash tools/verify/run.sh verify` riêng; reviewer không chạy cổng. Mã thoát: **chưa có — pending, xem `F:/App/qa-results/multi-floor/be-verify.log`** (lúc viết, log mới tới "created: 6/6 workers", chưa có dòng `exit=N`).
- Độ phủ: chưa đo (chờ log cổng). Đọc mã: `start.py:102` là biểu thức điều kiện trên một dòng, nhánh có `crop` không được test nào chạy nhưng coverage nhánh của coverage.py không bắt được (finding 2).
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước (`2026-11-01-feature-lb-01-lighting-bake.md`). Nợ ghi vào `changes/<mã>.md`.

## Phạm vi và điều kiện dừng sớm

- Cây sạch. Một commit `5b4ddccc feat(drawings): crop one floor out of a multi-plan sheet`, dòng đầu đúng mẫu, có `Prompt: MULTI-FLOOR-01`. Nhánh chưa lên `origin` (dự kiến: chưa duyệt). 11 file, +259/−10; mã ngoài test ~95 dòng (< 400, không có MNT-05).
- Không `pragma`, `type: ignore` mới, `noqa` trần, skip/xfail mới, không hạ ngưỡng; không chạm `uv.lock`, `pyproject.toml`, `openapi.json` gốc, `tools/**`, `tools/contract/APPFRONT_SHA`.
- **Dừng sớm §2, không đạt (hai lý do):**
  1. Không có `changes/MULTI-FLOOR-01.md` (BE-00 §13.2).
  2. `5b4ddccc` sửa `docs/charter/BE-00.md` (W14: `crop` tuỳ chọn) và `docs/charter/BE-BIND.md` (hàng #5) **cùng** `.py`, và **không** có trailer `Charter-Approved:`. Không tìm thấy bản duyệt của người dùng trong thân commit hay trong repo. Tiền lệ: `2026-11-01-feature-lb-01-lighting-bake.md` (REJECT cùng lý do; LB-01 sửa bằng commit `249b7c29 docs(charter): …` chỉ tài liệu, `Charter-Approved: changes/LB-01.md (người dùng duyệt 2026-11-01)`).
- `docs/contracts/openapi.json` là file chỉ người điều phối sửa (BE-00 §2 dòng 82, §12 bước 8). Diff của nó khớp đúng schema mới (`CropRect`, `InitUploadBody.crop`). Chấp nhận nếu phiên tác giả là điều phối của MULTI-FLOOR-01, nhưng nên tách thành commit `chore(contract): …` như tiền lệ (`ccea7c8e`, `0aa2680f`) — Nit 6.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| A | **§2 REJECT** | BE-00 §13.2 / merge-review §2 | Thiếu tệp bàn giao `changes/MULTI-FLOOR-01.md` | `changes/` | Thêm `changes/MULTI-FLOOR-01.md`: phạm vi, hợp đồng #5 mới, migration, nợ (finding 1–3), bằng chứng cổng (`exit=N` từ `be-verify.log`) |
| B | **§2 REJECT** | BE-00 §2 / merge-review §2 | Commit sửa `docs/charter/BE-00.md:156` (W14) và `docs/charter/BE-BIND.md:29` (#5) cùng mã, không có `Charter-Approved:` trỏ tới bản duyệt thật | `5b4ddccc` | Đưa câu chữ W14 + hàng #5 cho người dùng duyệt. Nhánh chưa lên `origin`, viết lại được: tách thành (1) `docs(charter): MULTI-FLOOR-01 crop on #5` **chỉ** hai tệp charter, trailer `Charter-Approved: changes/MULTI-FLOOR-01.md (người dùng duyệt <ngày>)` hoặc câu duyệt; (2) `feat(drawings): …` phần mã + migration + test; (3) `chore(contract): openapi crop on #5`. Cây cuối không đổi |
| 1 | P2 | DB / CON (thứ tự merge) | Hai head alembic khi gộp: nhánh `feat/library-file-models` (`f7585326`, `Prompt: LIB-FILES`, có trong `git log --all`, chưa vào `main`) thêm `r20261102_lib_decor_group` với `down_revision = "r20261102_lb_01"`, đúng bằng `down_revision` của `r20261102_mf_01` ở đây. Hiện tại so với `main` nhánh này chỉ có một head, nhưng nhánh nào vào `main` sau sẽ làm `alembic upgrade head` hỏng ("multiple heads") và bước 6 (migrate_check) đỏ. Thêm nữa: DB của f14 đang ở `r20261102_lib_decor_group`, nên chạy `alembic upgrade head` bằng mã của nhánh này trên f14 sẽ báo không tìm thấy revision đó. Hai nhánh cũng cùng sinh lại `docs/contracts/openapi.json` → xung đột khi gộp | `packages/db/migrations/versions/r20261102_mf_01_upload_crop.py:19`; `f7585326:packages/db/migrations/versions/r20261102_lib_decor_group.py:19` | Chốt thứ tự merge. Nhánh vào sau đổi `down_revision` sang head của nhánh vào trước (vd. `r20261102_mf_01` → `Revises: r20261102_lib_decor_group`) rồi chạy lại bước 6, hoặc thêm revision merge rỗng. Sau lần merge thứ hai, người điều phối chạy `run.sh openapi` và chép lại `docs/contracts/openapi.json`. Thử trên f14 thì `alembic upgrade r20261102_mf_01` không dùng được khi DB đang ở head của LIB-FILES: chỉ `ALTER TABLE uploads ADD COLUMN crop_corners JSONB` bằng tay hoặc vá `down_revision` cục bộ |
| 2 | P3 | TEST-01 | Đoạn nối duy nhất từ DB sang worker không có test: `_gd1` đổi `upload.crop_corners` (list JSONB) thành `Corners` cho `PageSource`. Test `choose_path`/`prepare_page` dựng `PageSource` bằng `replace(..., crop=...)` nên không đi qua `start.py`. Cùng một dòng nên coverage nhánh không bắt được | `apps/worker/pipeline_orchestrate/start.py:102` | Thêm một test GD1 (Postgres thật, như các test `start` hiện có): lượt tải có `crop_corners` → kế hoạch `kind="user"`, `corners` = 4 góc đã lưu, kiểu `tuple[tuple[float, float], ...]` |
| 3 | P3 | LOG | Đường có `crop` thay hẳn (iii) bằng (ii): không chạy `find_frame`/`drawing_quad` bên trong vùng cắt, nên khung tên/nét viền nằm trong vùng người dùng khoanh sẽ được giữ lại. Với PDF vector, `pixel_vectors` vẫn đọc tỉ lệ `TL 1:N` từ chữ của **cả tờ** (`parse_scale_note([vectors.text])`); tờ nhiều mặt bằng hay có chi tiết tỉ lệ khác, nên có thể lấy nhầm tỉ lệ. Nét ngoài vùng thì đã bị lọc theo tâm (`inside`) nên không lẫn tầng khác | `apps/worker/pipeline_orchestrate/preprocess.py:150-152`, `:260-261`; `packages/vision/walls/pdf_walls.py:347-348` | Chấp nhận cho lát này; ghi làm nợ trong `changes/MULTI-FLOOR-01.md`. Hướng sau: chạy (iii) trên ảnh đã cắt, và lọc lớp chữ theo vùng cắt trước `parse_scale_note` |
| 4 | Nit | API / tài liệu | BE-BIND ghi "sai → 422 `field:"crop"`", docstring `CropRect` ghi `field="crop"`, nhưng lỗi theo từng khoá trả `field` dạng `crop.xRatio`…; test cũng chỉ kiểm `startswith("crop")` | `docs/charter/BE-BIND.md:29`; `apps/api/drawings/schemas.py:66`; `apps/api/drawings/tests/test_routes_init.py:346` | Sửa câu chữ thành "`field` bắt đầu bằng `crop`" khi đưa người dùng duyệt (finding B) |
| 5 | Nit | MNT | `crop_corners: Mapped[Any]`; các cột JSONB khác trong `packages/db/models` khai kiểu cụ thể (`Mapped[list[str] \| None]`, `Mapped[dict[str, float] \| None]`) | `packages/db/models/drawings.py:64` | `Mapped[list[list[float]] \| None]` |
| 6 | Nit | OPS | `docs/contracts/openapi.json` nằm trong commit `feat`; tên nhánh không theo mẫu `<loại>/<mã>-<mô tả>` (BE-00 §13.2: nên là `feat/multi-floor-01-…`) | `5b4ddccc`; tên nhánh | Tách openapi khi làm finding B; tên nhánh không cần đổi |
| 7 | Nit | PERF | Mỗi tầng cắt từ cùng một tờ là một lượt tải riêng, nên tệp gốc (tới 100 MiB) được lưu và dựng trang N lần | `apps/api/drawings/uploads.py:213` | Chấp nhận cho lát này; khi cần, dùng lại tệp gốc theo `content_sha256` |

Đã soát, không có finding:
- **SEC**: `CropRect` là `WireRequest` (`extra="forbid"`, có test khoá lạ); mỗi tỉ lệ `ge=0, le=1`; NaN/Inf bị `le` chặn (đã thử trên pydantic 2.13.5: `nan` → `less_than_equal`); vùng phải nằm trong trang (dung sai 1e-6) và diện tích ≥ 0,01; góc kẹp về `[0, 1]`. Không có đường dẫn, tệp hay SQL thô mới. Quyền `floor.upload` không đổi.
- **CON**: `_twin_upload` thêm `crop_corners` vào khoá chống trùng: gửi lại cùng `crop` → cùng lượt, `crop` khác trên cùng tờ → lượt mới (có test trên Postgres thật). `== None` của SQLAlchemy sinh `IS NULL`, nên các lượt không `crop` vẫn khử trùng như cũ.
- **LOG**: `choose_path` giữ thứ tự ưu tiên: (i) dùng lại và (ii) góc #31 của **chính** lượt tải này vẫn thắng `crop`; chỉ các chỗ trước đây về (iii) mới đổi sang góc vùng cắt (test tham số hoá 4 ca + 1 test giữ reuse/góc người dùng). Ảnh raster đã `exif_transpose` (`packages/vision/preprocess/raster.py:118`), khớp với "trang gốc như trình duyệt hiện" của hợp đồng. `px_per_paper_mm` nhân `quad_scale` nên vẫn đúng khi cắt. Góc lưu vào `quality_assessments` là góc vùng cắt, #31 sau đó mở đúng vùng.
- **DB/API**: migration chỉ mở rộng (thêm cột `JSONB NULL`, không default, không backfill, chỉ sửa catalog), có `downgrade`; `none_as_null=True` nên `None` thành SQL `NULL`. Hợp đồng #5 chỉ thêm trường tuỳ chọn, thân trả không đổi (test kiểm `"crop" not in response`), FE cũ không gãy.
- **TEST**: negative case đủ (âm, > 1, tràn x, tràn y, quá nhỏ, thiếu khoá, khoá lạ), ca biên dung sai làm tròn, test pixel thật cho đường cắt (800×600 → 400×300).
- **RES/OBS**: không có phụ thuộc, timeout hay log mới.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 4,5 | 0,45 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4 | 0,40 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,67 / 5

## PHÁN QUYẾT: REJECT

Dừng sớm theo §2: thiếu `changes/MULTI-FLOOR-01.md` (A), và commit sửa `docs/charter/*` cùng mã mà không có `Charter-Approved:` (B). Phần mã không có P0/P1: validate ở biên chặt, chống trùng đúng, thứ tự ưu tiên trong `choose_path` hợp lý, migration chỉ mở rộng. Qua được A và B thì phần mã đủ điểm APPROVE, miễn là cổng đầy đủ xanh.

Để được duyệt ở lượt sau:
1. Thêm `changes/MULTI-FLOOR-01.md`, ghi finding 2, 3 (nếu chưa sửa) và 7 làm nợ (A).
2. Người dùng duyệt câu chữ W14 và hàng #5 của BE-BIND (sửa luôn Nit 4). Tách `5b4ddccc` thành commit charter chỉ tài liệu mang `Charter-Approved: …`, commit mã và commit `chore(contract)` cho openapi (B, Nit 6).
3. Dán bằng chứng cổng: `F:/App/qa-results/multi-floor/be-verify.log` kết thúc `exit=0` cho đúng cây cuối (viết lại lịch sử mà cây không đổi thì dùng được log này; nếu có thêm mã, ví dụ test ở finding 2, thì chạy `run.sh verify --fast` rồi cổng đầy đủ một lần nữa).
4. Trước khi merge: chốt thứ tự với `feat/library-file-models` (finding 1). Nhánh vào sau phải nối `down_revision` vào head của nhánh vào trước, chạy lại bước 6, rồi sinh lại `docs/contracts/openapi.json`.
5. Nên làm cùng lượt (không chặn): finding 2 (một test GD1), Nit 5.
