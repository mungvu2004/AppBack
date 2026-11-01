# Review merge feat/library-file-models → main

- Ngày: 2026-11-02 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 549059764afe (trên `origin/main` sau `git fetch`)
- Cổng: phạm vi **đầy đủ**, vì đây là review lượt 1 (R-33b điều kiện 1). `bash tools/verify/run.sh verify` chạy từ worktree tại 54905976: **mã thoát 0**, 18 phút 12 giây (02:37:29 → 02:55:41; log `F:/runs/can-mau/library-import/review-gate-full.log`; log cổng `.cache/src-out/verify/20261101T193814Z-549059764afe.log`, SHA khớp HEAD). Bước 0–8 và 5b đều **đạt**: pytest 9487 passed (15 phút 02 giây; `test_sweep_resends_quality_check`, hỏng ở lượt của tác giả, lượt này đạt); 5b perf 4 test + `case_gate` đạt; 6 `migrate_check` đạt (37 revision, đúng 1 head, lên/xuống/lên lại, model khớp DB, tên CHECK khớp model); 7 H1/H3/H4/H5 đạt với AppFront @ 607c71db; 8 openapi xuất được. Trước khi chạy: C: còn 59,0 GB, worktree không có `web-ctx-*`. `f14-ml-1` dừng trong lúc chạy rồi bật lại. Cổng dùng Postgres/Redis/MinIO của f14 (PERF-10). Cảnh báo `Combined 1 file, 1 file errored` của `coverage json` là tệp dữ liệu tạm hỏng, đã gặp ở các lượt trước, cổng vẫn đạt.
- Độ phủ: tổng dòng 99,40 % · nhánh 97,61 % | `apps/api/library` 98,63 / 97,62 · `packages/db` 97,53 / 95,90 · `packages/domain` 99,86 / 98,98 · `tools` 98,76 / 96,52 · tập file bị chạm 98,88 / 95,45.

## Phạm vi và điều kiện dừng sớm

- Cây sạch. Bốn commit trên `origin/main`: `f7585326 feat(library): …`, merge `origin/main` (merge do git tạo; không có trailer, như tiền lệ LB-01), `dd2af0a3 fix(library): …`, `54905976 docs(library): …`. Mọi commit không phải merge đều có `Prompt: LIB-FILES` và dòng đầu đúng mẫu. Nhánh chưa lên `origin` (đúng dự kiến khi chưa duyệt). Có `changes/LIB-FILES.md`.
- 24 file, +1126/−44. Bỏ `files.json` (dữ liệu), test và tài liệu thì còn 333 dòng logic thêm, dưới ngưỡng 400 của MNT-05.
- Không có `pragma: no cover/branch`, `# type: ignore` mới, `# noqa` trần, skip/xfail mới, cũng không hạ ngưỡng. Không chạm `docs/charter/*`, `uv.lock`, `pyproject.toml`, `openapi.json` ở gốc, `tools/verify/*`.
- Tệp chỉ người điều phối được sửa: `docs/contracts/openapi.json`, `docs/contracts.toml`, `tools/contract/APPFRONT_SHA`. **Chấp nhận** theo tiền lệ `2026-11-01-feature-lb-01-lighting-bake.md` và `2026-11-02-feat-multi-floor-sheet.md`, vì phiên tác giả điều phối cả hai phía FE và BE của LIB-FILES (có `commit-fe*.txt` và `merge-fe.txt` trong `F:/runs/can-mau/library-import/`). Đã kiểm từng tệp:
  - `APPFRONT_SHA` = 607c71db. Commit này có ở `origin/master` của AppFront và là hậu duệ của 45b6874c, ghim hiện tại của `main`. Schema FE @ 607c71db (`src/api/schemas/library.ts:83,137`) nhận `decor`, và `attribution: z.string().min(1).optional()`.
  - `openapi.json` chỉ khác ở `LibraryGroup` (+`decor`) và `LibraryItemOut.attribution`.
  - `contracts.toml` chỉ thêm `r20261102_lib_decor_group`, đúng revision mang dấu `# contract:`.
  - Ba tệp này nên đi thành commit `chore(contract)` riêng (Nit 4).
- Finding 1 của review MULTI-FLOOR-01 (hai head alembic) **đã xử lý**: `down_revision = "r20261102_mf_01"` (`packages/db/migrations/versions/r20261102_lib_decor_group.py:19`), và bước 6 xác nhận chỉ có 1 head.

## Kiểm gói tệp GLB (ngoài git)

Đã chạy `measure_glb` của chính nhánh này trên cả 63 tệp ở `F:/runs/can-mau/library-import/out`. Script nằm ngoài repo, nạp nguyên văn `glb.py`, chỉ đổi dòng `type _Mat` cho Python 3.11 của máy chủ. Kết quả:
- Đủ 63 `<id>.glb` và 63 `<id>.png`.
- `sha256` của **63/63** tệp khớp `files.json`.
- Mọi mục có rộng, sâu, cao và số tam giác dương. Mỏng nhất là `rug-rect-hq`, cao 34 mm. Lớn nhất 1,35 MB.
- Vì vậy với gói hiện tại, CHECK `published` không bị vi phạm.

Manifest có giấy phép CC-BY 4.0 (34 mục), MIT (21) và CC0 (8). Cả 34 mục CC-BY đều có `author`, nên `attribution` luôn có dạng "tác giả · giấy phép" và không bao giờ rỗng (khớp `min(1)` của FE).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG / SEC (validate ở biên) | `_file_plan` đo tệp **trước** khi so `sha256`. Mọi tệp tên `<id>.glb` trong thư mục đều bị `measure_glb` phân tích, kể cả tệp sai hay hỏng. Có những lỗi nằm ngoài ba loại được bắt `(ValueError, KeyError, IndexError)`: chunk JSON là mảng hay chuỗi, hoặc `nodes[i]` không phải object, sẽ ném `TypeError`/`AttributeError`; `children` tạo vòng thì lặp vô hạn. Khi đó cả lệnh `import-files` dừng giữa chừng, không ra `failed`. Thêm nữa, tệp đúng sha nhưng có một chiều làm tròn về 0 mm (tấm phẳng) sẽ được `put` lên storage, rồi `UPDATE` mới vi phạm CHECK `published` và ném `IntegrityError`, để lại object mồ côi. Gói hiện tại không gặp trường hợp nào (đã kiểm ở trên), nên đây là P3 | `apps/api/library/assets.py:228-236`; `packages/db/models/library.py:56-63`; `apps/api/library/assets.py:165` | So `hashlib.sha256(data).hexdigest()` với `item.model_sha256` trước khi gọi `measure_glb`, như vậy chỉ byte đã có trong manifest mới được phân tích. Trong `_file_plan`, coi mục có chiều hoặc số tam giác ≤ 0 là `failed`. Thêm test cho cả hai trường hợp |
| 2 | P3 | TEST-01 (negative case) | Không test nào chạy qua nhánh `library_file_unreadable`. Hai test import (`test_assets.py`, `test_jobs_cli.py`) chỉ ghi GLB hợp lệ với sha sai. `test_glb.py` chỉ thử byte không phải GLB; chưa thử hai nhánh "GLB thiếu chunk JSON đầu" và "GLB không có mesh nào trong scene". Log lỗi (`library_file_sha_mismatch`, `library_file_row_missing`) cũng chưa được khẳng định bằng `caplog`. Độ phủ gói vẫn ≥ 90/90 nên cổng không bắt được | `apps/api/library/assets.py:231-233`; `packages/domain/library/glb.py:229,262`; `apps/api/library/tests/test_assets.py` (`test_import_files_publishes_file_items`) | Thêm một tệp `b"glTF…"` hỏng vào thư mục của test import và khẳng định `failed` cùng log. Thêm hai ca có tham số cho `measure_glb`: chunk đầu là BIN, và scene không có mesh |
| 3 | P3 | OPS | Gói 63 tệp nhị phân mà sản phẩm cần chỉ nằm ở `F:/runs/can-mau/library-import/out` trên một máy. Repo chỉ có sha. Mất thư mục này thì 63 dòng mãi chưa phát hành: ẩn khỏi danh sách, không lỗi, nhưng thư viện mất 63 mẫu. Muốn dựng lại phải có worktree AppFront `welcome-can-mau` cùng Chrome (README của gói). `changes/LIB-FILES.md` không ghi nợ này | `docs/SETUP.md:130`; `changes/LIB-FILES.md` | Ghi một dòng nợ vào `changes/LIB-FILES.md`, hoặc chép gói lên nơi bền (Drive Train3D như các gói dữ liệu khác) và ghi đường dẫn vào SETUP.md |
| 4 | Nit | OPS | `openapi.json`, `contracts.toml` và `APPFRONT_SHA` nằm trong commit `feat`/`fix` chứ không ở commit `chore(contract)` riêng như tiền lệ | `f7585326`, `dd2af0a3` | Tách nếu viết lại lịch sử, hoặc ghi rõ trong commit gộp khi squash |
| 5 | Nit | MNT | `import_files` gộp `verified` (object đã có, không `put`) vào `published`, nên chạy lại lần hai vẫn báo `published=2` dù không ghi gì lên storage | `apps/api/library/assets.py:270` | Thêm `verified` vào `ImportReport` cho giống `PublishReport` khi chạm lại |

Đã soát và không thấy vấn đề:
- **SEC.** `item.id` qua `is_item_id` nên không có path traversal. CLI chỉ dành cho người vận hành. API chỉ thêm trường đọc.
- **CON.** Seed upsert idempotent. `import_files` và lịch `run_library_publish` chạm hai tập dòng tách nhau (`by_id.get` bỏ qua mẫu từ tệp; test cuối của `test_assets.py` khẳng định dòng không đổi). `published_at` được giữ khi sha không đổi.
- **K36.** Session đóng trước khi gọi storage.
- **DB.** Migration nới CHECK theo hướng thêm, mọi dòng cũ vẫn đạt. `downgrade` xoá dòng `decor`; hiện chưa có đường tạo mục của người dùng nên không mất dữ liệu người dùng.
- **API.** Trường `attribution` tuỳ chọn và được bỏ khi `None` (test khẳng định khoá vắng).
- **MNT.** Hàm nào cũng có docstring.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,79 / 5

## PHÁN QUYẾT: APPROVE

Nhánh không dính điều kiện dừng sớm nào ở §2:
- có tệp bàn giao;
- commit đúng mẫu;
- tệp của điều phối được chấp nhận theo tiền lệ, đã kiểm ghim AppFront và nội dung diff.

Cổng đầy đủ thoát 0 ở cả 8 bước và 5b. Độ phủ của mọi gói bị chạm ≥ 90/90. Migration đã nối sau `r20261102_mf_01` và chỉ còn 1 head. 63/63 tệp GLB khớp sha của manifest và đo ra số dương.

Không có P0, P1 hay P2. Ba P3 và hai Nit không chặn merge. Nên sửa finding 1 và 2 ở lát sau, hoặc ghi chúng cùng finding 3 thành dòng nợ trong `changes/LIB-FILES.md`. Merge do phiên gọi thực hiện. Nếu squash, ghi rõ trong commit gộp rằng có ghim `APPFRONT_SHA` 607c71db và `docs/contracts/openapi.json` đã sinh lại.
