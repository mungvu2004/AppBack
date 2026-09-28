# Review merge feature/b2-06-glb-library → main

- Ngày: 2026-09-28 · Reviewer: phiên `/merge-review` (độc lập, R-37) · Commit đầu nhánh: `50fb5f78b83e`
- Commit vào main: `1e1d765` (bảng) · `d433397` (miền A) · `1834941` (gộp A+B, merge 2 cha) · `9e45fcf` (API C) · `50fb5f7` (`docs(contract)` của điều phối viên)
- Cây làm việc: sạch · dòng đầu mọi commit đúng Conventional Commits, đủ trailer `Prompt: B2-06` · `changes/B2-06.md` có (9 dòng)
- Cổng: **Phạm vi kiểm: đầy đủ — lượt đầu nhánh đi review (R-33b điều kiện 1, 2, 3, 5)**;
  `bash tools/verify/run.sh verify` **mã thoát 0** (log: `/tmp/b2-06-verify.log`, chạy trong pane RUNNER, container `appback-verify-b2-06-review-verify-run`)
- Độ phủ (lượt đầy đủ, `coverage_gate: đạt`): tổng **dòng 99,53% · nhánh 98,47%** · `apps/api/library` **99,56 / 95,45** ·
  `packages/domain` **100 / 100** · `packages/db` 96,58 / 95,76 · `packages/testing` 99,49 / 98,61 · tập file bị chạm 99,79 / 97,83 —
  mọi gói bị chạm và tổng đều ≥ 90/90
- Test: **5 146 qua, 0 hỏng, 7 deselected** (20 phút 46 giây)

## Bảng bước (mã thoát thật, không chép báo cáo tác giả)

| Bước | Lệnh | Trạng thái | Ghi chú |
|---|---|---|---|
| 0 | làm ấm `node_modules` | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 5 146 qua / 0 hỏng |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm |
| 6 | `lint_migrations` → `migrate_check` | đạt | 13 revision, 1 head, seed ci hai lần, downgrade base, model khớp DB, tên CHECK khớp |
| 7 | `tools.contract.check` | đạt | AppFront @ `9cf0b0bfffbd` |
| 8 | `openapi` | đạt | |

Bảng con bước 7: Smoke **đạt** (23 module, 83 mục) · Bản đồ đủ **đạt** (83/83) · Thao tác đã mount **đạt** (55/83) ·
**H1 đạt (1 263 mẫu response)** · H1 ngữ cảnh **đạt** (50) · H3 **đạt** (10 khoá, 3 vai) ·
H4 **không áp dụng** — B3-05 chưa hợp nhất, chưa có `apps.api.rules.catalog` (đúng BE-00 §12) · H5 **đạt** (4 khung SSE).

`case_gate` (bước 5b, **đạt**), thiếu = 0:
- `library_list_items` — bắt buộc `C01 C04 C05 C12 C13 C15 C17 C25`, tìm thấy đủ;
- `library_read_item` — bắt buộc `C01 C04 C05 C08 C12 C13 C17 C25`, tìm thấy đủ (`cases.toml` `extra = ["C08"]` đúng chỗ);
- task `publish_library_assets` — `test_publish_library_assets__J01`, `__J06` có, cổng đạt nên không in dòng thiếu.

## Kiểm độc lập của reviewer (không tin báo cáo tác giả)

1. **GLB đọc được bằng three.js** — tôi tự viết bộ đọc theo đặc tả glTF 2.0 và chạy trên cả 16 tệp: header `glTF`/2/tổng
   độ dài đúng; đúng 2 chunk, mỗi chunk chia hết 4, JSON đệm `0x20`, BIN đệm `0x00`; `asset.version == "2.0"`; có
   `scene: 0`, `scenes: [{nodes:[0]}]`, `nodes: [{mesh:0}]`; `buffers[0].byteLength` bằng đúng độ dài chunk BIN và **không**
   có `uri` (đúng luật GLB); mọi `bufferView` nằm trong BIN, `target` thuộc {34962, 34963} và đúng loại accessor;
   `byteOffset` của mọi khối `FLOAT` chia hết 4; `min`/`max` của `POSITION` **bằng đúng** đỉnh float32 thật trong BIN;
   mọi chỉ số nhỏ hơn số đỉnh; `material` chỉ có `pbrMetallicRoughness` với `metallicFactor 0`, `roughnessFactor 0.8`.
   **0 lỗi.** Không cần GLTFLoader (đọc tay theo spec là đủ, đúng phạm vi task).
2. **`UNSIGNED_INT` khi hơn 65 535 đỉnh** — dựng mục tổng hợp 2 800 khối (67 200 đỉnh): `componentType` = 5125. Đúng.
3. **Chiều quay tam giác** — tôi tính lại tích có hướng cho cả 6 mặt của `_FACES` (`glb.py:29-36`): cả 6 đều ngược kim
   đồng hồ nhìn từ ngoài, khớp pháp tuyến khai báo. Không mặt nào lộn (three.js không cull sai).
4. **Hộp bao bằng bảng [5]** — tính lại 16 mục từ `part_bounds`: **khớp từng số**, đối xứng quanh 0 theo X và Z, `min_y = 0`.
5. **Tất định** — dựng hai lần cho cùng byte (GLB và PNG). Byte GLB/PNG của tôi **trùng từng số** với bảng trong
   `bao-cao-B2-06.md`, dù tôi chạy Python 3.11 ngoài container (bản zlib khác) — xem F1 về ý nghĩa của điều này.
6. **PNG** — chữ ký, **CRC32 từng chunk**, IHDR `128×128/8/2/0/0/0`, thứ tự `IHDR→IDAT→IEND`, IDAT giải ra **đúng**
   `128 × (1 + 3×128)` byte và byte filter của **mọi** dòng bằng 0. 0 lỗi.
7. **Dây #14/#15** — khoá camelCase của `LibraryItemOut` **bằng đúng** 11 khoá của `LibraryItemSchema.strict()`
   (`AppFront/src/api/schemas/library.ts:124-152`); không `furnitureKind`, `ownerId`, `publishedAt` (K01); `previewUrl`
   **vắng khoá** khi NULL (`WireModel` bỏ `None`, W2/K02) và không nằm trong `required` của openapi — `anyOf string|null`
   trong openapi là hệ quả của Pydantic, dây thật không bao giờ ra `null` (test C17 khẳng định `"previewUrl" not in`).
8. **openapi.json** — so cấu trúc với `main`: thêm **đúng** 2 path (`/api/library`, `/api/library/{item_id}`) và **đúng**
   3 schema (`LibraryGroup`, `LibraryItemOut`, `LibrarySource`); **0** path/schema bị đổi hay xoá; #14 là mảng trần.
9. **Bản đồ hợp đồng** — `tools/contract/schema-map.ts:59-60` đã trỏ cả hai `op` sang `LibraryItemSchema`, nên H1
   (1 263 mẫu) thật sự giải hai op này, không bỏ qua. `docs/contracts.toml` không liên quan (chỉ là danh sách revision).
10. **ReDoS** — `is_item_id` (`catalogue.py:35`) kiểm **độ dài trước** rồi mới `fullmatch`, nên nhóm `(-[a-z0-9]+)*`
    không bao giờ nhận chuỗi dài; dùng `fullmatch` nên chuỗi có xuống dòng cuối không lọt (có test biên).
11. **Ranh giới nhập** — grep toàn `packages/**`: chỉ `packages/testing/**` nhập `fastapi`/`starlette`, nên hôm nay
    `assets.py`/`cli.py`/`jobs.py` không thể kéo tới chúng; hợp đồng `.importlinter` `api-jobs-no-web` phủ `jobs` và
    (qua đồ thị nhập) cả `assets`, **không** phủ `cli` — xem F2.
12. **CHECK `published` dùng `COALESCE(x,0) > 0`** (lệch của việc B) — **đúng và cần thiết**: `NULL > 0` cho `NULL`,
    mà CHECK cho `NULL` đi qua, nên không có `COALESCE` thì ràng buộc vô hiệu với cột NULL. Có test cho cả hai nhánh
    ("phát hành thiếu số đo", "phát hành thiếu khoá").
13. **Seed** — `ORDER = 50`, đủ 5 môi trường, chỉ ghi danh tính, `ON CONFLICT … DO UPDATE … WHERE is_distinct_from`
    nên chạy lại không chạm `updated_at`; rút/hiện lại có test; danh mục rỗng là no-op (chặn rút hàng loạt do tiêm sai);
    mục có chủ không bị rút; **không** dựng storage. Bước 6 "seed ci hai lần" đạt.
14. **Migration khớp model** — 18 cột, 6 CHECK, FK `ON DELETE RESTRICT`, index một phần: khớp từng dòng; `timestamptz`
    đến từ `Base.type_annotation_map` (K20); expand thuần (`create_table` + `create_index`), bước 6 "model khớp DB" đạt.
    FK `RESTRICT` (lệch của B) hợp lý và có lý do ghi trong docstring: `SET NULL` sẽ lặng lẽ biến mục riêng thành mục
    chung, `CASCADE` sẽ xoá mất mục, mà người dùng vốn chỉ xoá mềm.
15. **K36, K22, K16** — `_read_known` đóng session trước khi đụng storage; test đo thật `pool.checkedout() == 0` tại
    **mọi** lần `put` (6 lần với `batch=3`); `_record` chỉ chạy sau khi cả hai object `stat` lại khớp `sha256` **và**
    `kind`; URL chỉ qua `signed_url(key, disposition="attachment", filename=…)`, không `kind`, không `stat`, không hạn
    riêng — test đếm `stat` của #14 với 16 mục bằng **0**, URL cùng giờ giống hệt, qua mốc giờ thì khác.
16. **Quyền** — route chỉ `current_principal`, không `require_permission` (khoá `—`, đúng [7]); mục `mine` của người khác
    404 `resource:"libraryItem"` và vắng ở #14 (có test); id sai mẫu 404 trước khi truy vấn (`service.py:72-73`).
17. **Cấm** — không `pragma: no cover`/`no branch`, không `skip`/`xfail`, không hạ ngưỡng; một `# noqa: S603` và một
    `# type: ignore[misc]` đều **có mã kèm lý do**; không commit `.glb`/`.png`; `pyproject.toml`/`uv.lock` không đổi
    (không thư viện mới); không sửa file ngoài cột "Sở hữu" (`docs/contracts/openapi.json` do điều phối viên commit).
18. **Sổ nợ** — `DEBT.md` không có nợ `P0`/`P1` mở thuộc nhánh này. `NO-107` (P3) vẫn mở **đúng**: B2-06 không đọc
    principal từ DB nên điều kiện đóng chưa tới.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| F1 | P3 | LOG-04 | `preview_sha256` là sha của byte **đã nén zlib**, mà `zlib.compress` không cam kết giống nhau giữa các bản zlib. Hai tiến trình (hay một lần nâng ảnh nền) khác bản zlib thì `_needs_work` **luôn** đúng: mỗi phút `put` lại PNG, `UPDATE` lại dòng, và vì `_same_shas` sai nên `published_at` **bị đặt lại bằng now** mỗi lượt. Không lộ ra dây (K01 không trả `publishedAt`), nhưng là ping-pong ghi DB/storage vĩnh viễn và mốc phát hành mất nghĩa | `packages/domain/library/preview.py:47`; `apps/api/library/assets.py:96-107,151` | So "cần làm" của ảnh bằng sha của **scanline chưa nén** (`raw`), hoặc chỉ đặt lại `published_at` khi `model_sha256` đổi |
| F2 | P3 | TEST-03 | Test ranh giới chỉ chặn **3** gói; BE-00 §7 đòi **bốn** (`fastapi`, `starlette`, `jwt`, `argon2`) và 8 module khác trong repo đều dùng bộ 4. `.importlinter` phủ `apps.api.*.jobs` (và qua đồ thị cả `assets`) nhưng **không** phủ `cli.py`, nên không gì chặn `cli` kéo `starlette` về sau. Prompt cũng chỉ liệt 3, nên đây là lệch hiến chương mà không ghi vào "Lệch khỏi prompt" | `apps/api/library/tests/_helpers.py:21` | Thêm `"starlette"` vào `BLOCKED` (một từ); cân nhắc đổi tên thành `WORKER_BLOCKED` cho khớp 8 module kia |
| F3 | P2 | MNT-05 | Nhánh khoảng 1 295 dòng không phải test (khoảng 950 dòng logic sau khi trừ ~210 dòng dữ liệu danh mục và 87 dòng DDL) — vượt trần 400 dòng logic | toàn nhánh | **Chấp nhận**: nhánh đã dựng bằng 3 nhánh con theo `so_huu` (miền A, bảng B, API C) rồi gộp, đúng cách giảm rủi ro review; tách thêm không giúp gì vì GLB, lịch phát hành và dây phải kiểm cùng nhau (tiền lệ NO-091, NO-109). Cần một dòng `DEBT.md` |
| N1 | Nit | R-08 | `upgrade()` 54 dòng, vượt trần 50 (khai DDL phẳng, chỉ 2 câu lệnh; migration dài nhất trên `main` trước đây là 48) | `packages/db/migrations/versions/r20260928_b2_06_library.py:29` | Không đáng tách; ghi nhận để lần sau tách bảng và index thành hai `op.` gọn hơn |
| N2 | Nit | MNT-02 | `ORDER = 50` trùng `packages/db/seeds/spatial.py:35`. Vô hại: bộ chạy sắp theo `(ORDER, tên)` nên thứ tự vẫn tất định (`library` trước `spatial`), và `50` do prompt [5] chỉ định | `packages/db/seeds/library.py:21` | Người điều phối chọn số riêng cho seed sau; không sửa ở nhánh này |
| N3 | Nit | PERF-06 | `run_library_publish` dựng GLB và PNG cho **mọi** dòng trong danh mục rồi mới bỏ dòng vượt `batch`, nên chi phí dựng tỉ lệ với danh mục chứ không với `batch` (hôm nay 16 mục khoảng 0,02 s nên miễn phí) | `apps/api/library/assets.py:190-199` | Dừng dựng khi `attempted == batch` và không còn dòng nào cần đếm `skipped` |
| N4 | Nit | OBS-05 | Dòng vượt `batch` không vào bucket nào, nên bảng đếm của CLI không cộng lại thành số mục danh mục ở lượt chạy dở | `apps/api/library/assets.py:197-200`; `apps/api/library/cli.py:44-46` | Thêm `deferred` vào `PublishReport`, hoặc in thêm "còn N mục để lượt sau" |
| N5 | Nit | TEST-07 | `test_build_all_assets_under_one_second` khẳng định theo đồng hồ thật (biên 1 s cho khoảng 0,02 s việc thật) | `packages/domain/library/tests/test_catalogue.py:113` | Dư 50 lần nên rủi ro flake thấp; nếu CI chậm thì đổi sang marker `perf` |

Không có finding P0, không có P1.

## Lệch khỏi prompt — đối chiếu từng mục

| Lệch tác giả nêu | Phán quyết |
|---|---|
| `sort_order` bằng chỉ số nhân 10 | **Chấp nhận** — `CatalogueItem` không có `sort_order`; tất định, chừa chỗ chèn; có test |
| CHECK `published` dùng `COALESCE(x,0) > 0` | **Chấp nhận, và là bản sửa đúng** — xem kiểm độc lập §12 |
| FK `owner_id ON DELETE RESTRICT` | **Chấp nhận** — lý do đứng được, ghi trong docstring model |
| Thêm `packages/domain/library/tests/__init__.py` | **Chấp nhận** — đúng đính chính của điều phối viên (`coverage_gate.py:155`) |
| `PublishReport` có thêm `verified`; mục lệch sau `put` tính `failed` | **Chấp nhận** — thông tin nhiều hơn prompt đòi, không đổi hành vi |
| `sync_catalogue(())` là no-op | **Chấp nhận** — chặn rút hàng loạt do tiêm sai, và `insert().values([])` vốn không hợp lệ; có test |
| `open_storage(clock)` ở `assets.py` cho cả `jobs` và `cli` | **Chấp nhận** — đúng tinh thần BE-00 §7 (vẫn là `create_storage`), tránh lặp (R-07), nhập trễ có lý do ghi rõ |
| Test tên `test_library_*` cho lô, tự lành, K36, lỗi storage | **Chấp nhận** — J-case chỉ dành cho J01/J06, đúng CASE.md |
| `preview_sha256` phụ thuộc bản zlib | **Thành finding F1** — tác động lớn hơn "vô hại" như báo cáo viết (ping-pong cộng `published_at` bị đặt lại) |
| Chỉ chặn 3 gói trong test ranh giới | **Không nêu trong báo cáo, thành finding F2** (hiến chương đòi 4) |

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 4 | 0,60 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 4 | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 3 | 0,09 |
| **Tổng** | **100%** | | **4,72 / 5** |

## PHÁN QUYẾT: APPROVE (4,72/5)

Không P0, không P1, điểm từ 4,0 trở lên → đủ điều kiện merge theo ma trận `RULE.md` §5.

Nhánh này chắc tay ở đúng hai chỗ khó nhất của prompt. Thứ nhất, tệp `.glb` **thật sự** đúng đặc tả glTF 2.0: tôi tự
viết bộ đọc theo spec và không tìm được một vi phạm nào trên cả 16 tệp, kể cả những chỗ dễ sai lặng lẽ nhất —
`min`/`max` khớp đỉnh float32 (không phải đỉnh mm), `byteOffset` của `FLOAT` chia hết 4, `buffers[0]` không có `uri`,
và cả 6 mặt hộp quay ngược kim đồng hồ nhìn từ ngoài. Thứ hai, lõi phát hành giữ đúng K22 và K36 bằng thiết kế chứ
không bằng lời hứa: `published_at` chỉ được ghi sau khi `stat` lại khớp cả `sha256` lẫn `kind`, và test **đo thật**
`pool.checkedout() == 0` ở mọi lần `put` thay vì chỉ đọc mã. Test dùng Postgres và storage thật (`local_storage` và
`s3_storage`/MinIO), không mock một dịch vụ nào (K23), và phủ đủ mọi gạch của khối [8] kể cả tự lành, mất object ngoài
luồng, storage sập, và ranh giới nhập trong tiến trình con.

Ba việc cần làm **sau** khi merge (không chặn merge):
1. **F1** — sửa gốc cách so "cần làm" của ảnh xem trước, hoặc giữ `published_at` khi chỉ sha ảnh đổi. Đây là nợ tác giả
   đã nêu nhưng đánh giá nhẹ hơn thực tế.
2. **F2** — thêm `"starlette"` vào `BLOCKED` (một từ) để khớp BE-00 §7 và 8 module còn lại.
3. **F1, F2, F3** cần dòng `NO-<nnn>` trong `DEBT.md` (R-34) — phiên review không được sửa `DEBT.md`, người điều phối ghi.

Việc merge thuộc phiên gọi review này; tôi không merge.
