# Review merge fix/b0-04-key-layout-debts → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả; mọi khẳng định trong commit, `DEBT.md` và báo cáo `W11-KEYLAYOUT.report.md` đều tự kiểm lại) · Commit đầu nhánh: `f45112f22854`. Nhánh có 7 commit: `b2864d9` FIX-054 (B0-02), `5c8586a` FIX-055 (B0-04), `271382b` FIX-056 (B0-02), `318dc5b` FIX-057 (B0-04), `778c052` FIX-058 (B5-01), commit gộp `main` `adcf687` (cha `778c052`, `334d73c`) và `f45112f` ghi NO-081. Merge-base = `334d73c`; phạm vi = `git diff main...HEAD` (9 file: `DEBT.md`, `packages/core/{ids.py, object_keys.py, tests/test_ids.py, tests/test_object_keys.py}`, `packages/storage/{keys.py, tests/test_keys.py}`, `packages/ml_contracts/{payloads.py, tests/test_payloads.py}`; +243/−66 dòng). **`main` đã đi thêm** tới `89943528fe04` (gộp `fix/b1-01-parallel-refresh-flake` rồi ghi NO-083..086) — chỉ chạm `DEBT.md`, `docs/fixes.md`, `apps/api/auth/tests/test_refresh.py`, một file `docs/reviews/`; không file nào của `packages/{core,storage,ml_contracts}`, `apps/ml`. `git merge-tree` với `main` hiện tại: **xung đột duy nhất ở `DEBT.md`** — xem điều kiện merge 1.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**, lấy từ hai nguồn trùng nhau: dòng `EXIT=0` của chính shell bọc (không bị cắt) và `MSYS_NO_PATHCONV=1 docker wait appback-verify-appback-fix-storage-verify-run-274b3f7a088a` = `0` (chạy song song `docker logs -f` ra file). Lượt 05:02:38Z–05:07:55Z trên `f45112f22854`; ngay trước đó `docker ps -q --filter name=verify-run | wc -l` = 1. Log: `verify.log`, `verify.docker.log`, `verify.wait` trong scratchpad của phiên review. Bước 5: **2089 passed, 0 failed, 10 skipped**, 1 deselected, 261,4 s; cả 10 skip là `apps/api/core/tests/test_common.py` (`ssssssssss` — tập tham số rỗng, chưa có route được bảo vệ), đúng ngoại lệ BE-00 §12, file y hệt `main`.
- Độ phủ (in từ `tools.coverage_gate` của lượt trên, không lấy từ báo cáo tác giả):
  - tổng: dòng **99,35 %** · nhánh **97,52 %**
  - `packages/core`: dòng **100,00 %** · nhánh **100,00 %** · `packages/ml_contracts`: **99,90 %** · **99,56 %** · `packages/storage`: **99,64 %** · **98,28 %**
  - tập file bị chạm: dòng **100,00 %** · nhánh **100,00 %**. Không dòng nào rơi vào sai số NO-035 (bốn module không đi qua SQLAlchemy).

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (325 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (281 file) |
| 4 | `lint-imports` | đạt (9 kept, 0 broken — gồm `packages.core không nhập gói nội bộ khác…` KEPT) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf 1 passed; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5; ba cảnh báo route hạ tầng có từ trước) |
| 6 | `lint_migrations` → `migrate_check` | đạt (4 revision; 10/10) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt — H1 186 mẫu; H3/H4/H5 `không áp dụng` **hợp lệ** (B1-02, B3-05, B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (đầu phiên và cuối phiên) |
| `changes/B0-02.md`, `changes/B0-04.md`, `changes/B5-01.md` tồn tại | đạt (có từ các prompt gốc; FIX không bắt buộc sửa mảnh) |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt — 7 commit, dài nhất 67 ký tự; `fix`/`chore`/`docs` đúng loại |
| Trailer đọc được (R-36b) | đạt — `%(trailers:key=Prompt,valueonly)` ra `B0-02`, `B0-04`, `B0-02`, `B0-04`, `B5-01`, `B0-04`, `B0-04`; năm commit FIX ra đúng `Fix: FIX-054` … `FIX-058`; commit gộp và commit sổ không `Fix:` |
| Dòng `DEBT.md` đổi trong **chính** commit sửa | đạt — NO-076 `✅` trong `5c8586a` (FIX cuối của cặp 054/055), NO-077 `✅` trong `778c052` (FIX cuối của bộ ba 056..058) |
| Đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/**` | không |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không — một `# type: ignore[arg-type]  # kiểm lúc chạy` mới có mã và lý do (`test_ids.py:118`), y hệt lối của `test_ids.py:72` |
| `conftest.py` lồng, file cấu hình công cụ riêng, thư viện mới | không (`object_keys.py` chỉ nhập thêm `packages.core.ids`) |
| File ngoài phạm vi [4] của FIX-054..058 | `check_id` vào `packages/core/ids.py` trong commit FIX-056 ([4] của FIX-056 chỉ ghi `object_keys.py`) — cùng chủ B0-02, người điều phối đã duyệt (phương án A, `check_id` cạnh `is_id`), tác giả ghi ở "Lệch khỏi prompt". `DEBT.md` theo luật của đoạn giao việc |
| Nhánh > 400 dòng logic (MNT-05) | không — +243/−66 gồm test và `DEBT.md` |

Không có điều kiện dừng sớm nào kích hoạt.

## Công cụ kiểm tại chỗ

Probe chạy trong container verify (`run.sh shell < probe.sh`, bản sao `/tmp/w`); file của commit cũ đặt tạm ở `.cache/rv-keylayout/` (git-ignore), chép đè trong bản sao, **đã xoá** cuối phiên. Hai lượt probe. **Lệch quy trình, tự khai:** lượt probe 1 được khởi chạy khi `docker ps … | wc -l` in `2` (lượt verify của chính phiên này còn chạy cùng một lượt verify của worktree khác) — lệnh đếm nối bằng `&&` nên không chặn; ba container sống cùng lúc trong thời gian lượt probe chạy, không lượt nào hỏng, mã thoát cổng không bị ảnh hưởng (lượt verify đã chạy tới bước 5 và thoát 0). Lượt probe 2 có điều kiện `n < 2` thật (đếm = 1).

- **P1 — đỏ trước / xanh sau từng FIX** (test của nhánh chạy trên mã của commit cha, rồi trên mã của nhánh):

  | FIX | Test chặn tái phát | Mã cũ đặt vào | Trước | Sau | Khớp dòng `DEBT.md`? |
  |---|---|---|---|---|---|
  | 054 | `test_is_ulid` (13 ca), `test_is_id_reads_ulid_rule_of_is_ulid` (`test_ids.py` @ `b2864d9`) | `ids.py`, `object_keys.py`, `storage/keys.py`, `payloads.py` @ `334d73c` | **14 failed** (`AttributeError: … has no attribute 'is_ulid'`) | 14 passed; cả file 54 passed | ✓ "đỏ 14 failed → xanh 14 passed" |
  | 055 | `test_avatar_name_follows_ulid_rule_of_core` (HEAD) | `storage/keys.py` @ `334d73c` | **1 failed** — lỗi ném từ id `usr_` (bản chép `_ULID_RE` cho tên ảnh qua), không từ tên ảnh | 1 passed | ✓ "đỏ 1 failed → xanh 1 passed" |
  | 056 | `-k "check_id or upload_prefix"` trên `test_ids.py` + `test_object_keys.py` (HEAD) | `object_keys.py` @ `334d73c`, `ids.py` @ `b2864d9`, `storage/keys.py` @ `5c8586a` | **27 failed** | 27 passed | ✓ "đỏ 27 failed → xanh 27 passed" |
  | 057 | `test_upload_layout_comes_from_core`, `test_server_chosen_kind_reads_id_rules_of_core` ×3 (HEAD) | `storage/keys.py` @ `334d73c` | **4 failed** (`is` sai; `'png' is None` ×3) | 4 passed; cả file 43 passed (keys cũ: 5 failed, 38 passed) | ✓ "đỏ 4 failed → xanh 4 passed" |
  | 058 | `test_upload_layout_comes_from_core` (`test_payloads.py` HEAD) | `payloads.py` @ `334d73c` | **1 failed, 89 passed** (`DID NOT RAISE ValidationError`) | 1 passed | ✓ "đỏ 1 failed → xanh 1 passed" |

  (Lượt probe 1 đặt riêng `ids.py`/`object_keys.py` cũ lên cây HEAD thì vỡ ở plugin `packages.testing.fixtures.api` — `ImportError: cannot import name 'check_id'`, vì plugin nhập `storage.keys` đã gọi `check_id`; lượt 2 đặt lại cả bộ file của đúng commit cha nên ra số trên.)
- **P2 — đột biến trên HEAD:**
  - M1 bỏ vế `key.startswith(prefix)` của `upload_prefix_of` → **4 failed** (ba khoá sai chữ bố cục `project/…`, `levels/…`, `upload/…` và `test_upload_prefix_of_rebuilds_with_upload_prefix`): kiểm "bằng dựng lại" có test chốt thật.
  - M2 `upload_prefix` kiểm tầng bằng regex chép tay `L-[0-9A-Z]{10,64}` thay `is_spatial_id` → **2 failed** (`test_upload_prefix_reads_id_rules_of_core_ids[is_spatial_id]` của core và `test_server_chosen_kind_reads_id_rules_of_core[is_spatial_id]` của storage).
- **P3 — tương đương hành vi:**
  - `is_id` cũ (`re.fullmatch(f"{prefix}_{_ULID_BODY}")`) và mới (`startswith` + `is_ulid`) trên **400 009** chuỗi (tiền tố `prj_`/`upl_`/`PRJ_`/rỗng, thân 0–31 ký tự từ Crockford + `I L O U`, chữ thường, `_`, `\n`, chữ số toàn khổ `０`, chữ số Ả Rập `١`): lệch **0**.
  - `_upload_prefix` cũ của `ml_contracts` (bản `334d73c`) và `upload_prefix_of` mới trên **180 000** khoá (ghép đoạn từ `projects/project`, `floors/levels`, `uploads/upload`, id đúng/sai/lẫn loại, `L-` 9 ký tự, đoạn rỗng, `..`; 1–8 đoạn đuôi): lệch nhận/từ chối và lệch tiền tố trả về **0**. Chỉ **thông báo** đổi: id sai ở vị trí id nay nêu trường (`id phải có dạng prj_<ULID>: 'prj_bad'`) thay vì "khoá không nằm dưới một lượt tải lên"; `define_task` chỉ ghi `exc.error_count()` (`packages/messaging/tasks.py:202-203`), không ai khớp chuỗi này ngoài test (grep).
- **P4 — quan sát (dẫn tới #1, #2):** `upload_prefix_of("…/uploads/{upl}/../../../../x")` và `upload_prefix_of("…/uploads/{upl}/pages//0.png")` **trả tiền tố, không lỗi**; `upload_prefix_of("ml/models/mdl_…/a/b/c/d.onnx")` → `id tầng sai mẫu L-<base36 HOA>: 'a'`; `InferStepPayload(page_key="ml/models/mdl_…/a/b/c/d.png")` → `Value error, id tầng sai mẫu …: 'a'`.
- **P5 — AST bốn module sản phẩm:** hàm dài nhất 23 dòng (`server_chosen_kind`, có từ trước); hàm mới `is_ulid` 7, `check_id` 9, `upload_prefix` 10, `upload_prefix_of` 12 dòng, CC ≤ 3, lồng ≤ 2; mọi hàm mới có docstring. Ba hàm test mới thiếu docstring (#4).
- **P6 — người gọi mọi API nhánh đổi** (grep toàn cây sau khi gộp `main` @ `334d73c`, gồm B0-06, B0-07, B1-01, B3-01 mới vào): `_entity_id`, `_level_id`, `keys._ULID_RE`, `payloads._upload_prefix`, `_ULID_BODY` — **0** người gọi còn lại. `is_id` (ngữ nghĩa giữ nguyên, P3) được gọi ở `packages/core/errors.py:16`, `apps/api/auth/tokens.py:27`, `apps/api/core/auth.py:17`, `packages/messaging/streams.py:18`, `packages/ml_contracts/payloads.py:20`. `keys.project_prefix`/`keys.upload_prefix` giữ tên (xuất lại, `is` đúng hàm lõi) cho `packages/storage/tests/{test_s3,test_local,test_contract}.py`. `main` @ `8994352` không thêm người gọi nào.

## Ranh giới `packages/core` sau nhánh (câu hỏi của người điều phối)

**Đứng được, với một điều kiện về sổ (#7).**

- Câu "`packages/core` chỉ có cấu hình nền" (BE-00 §2.1, ngay sau bảng) nói về **lớp cấu hình**: câu kế nó là "`DatabaseSettings` nằm ở `packages/db`". §2.2 đã giao cho `core` id có tiền tố, sổ mã lỗi, đồng hồ; `core` trên `main` còn có `pipeline.py` (`PIPELINE_STEPS`, từ vựng dùng chung mà chính `storage.keys` nhập) và `keys.py` (HKDF). Tức `core` vốn là nơi đặt **luật thuần, không I/O, dùng chung giữa các gói bị cấm nhập nhau** — `object_keys.py` (FIX-043) và phần nhánh thêm đúng loại đó. `lint-imports` hợp đồng `core-isolated` KEPT; `object_keys.py` chỉ nhập `re`, `typing`, `packages.core.ids`.
- Đường cắt nhánh chọn là "phần bố cục mà `ml_contracts` phải kiểm trong payload không tin": luật khoá + tiền tố dự án + tiền tố lượt tải lên. Mọi hàm dựng còn lại (đuôi, tên, số trang, `library`, `ml/models`, `ml/datasets`, ảnh đại diện) và `server_chosen_kind` (phụ thuộc `packages.storage.sniff.ImageKind`, phải ở `storage`) vẫn ở `storage.keys`. `core` **không** bị kéo thành nơi chứa bố cục storage: 2/7 họ khoá của BE-00 §8, đều là phần đầu mà các họ còn lại dựng lên trên.
- Rủi ro là đường cắt "theo ai cần" trôi dần: NO-081 (`runs/{run}/{step}/`, `ml/models/{mdl}/`) sẽ đưa thêm hai họ xuống `core`. Khi đó nên cân nhắc dời **cả** các hàm dựng thuần xuống `core.object_keys` và để `storage.keys` chỉ còn xuất lại + `server_chosen_kind`, thay vì ba nửa. Quyết định này và dòng §2.2 cho các tên mới thuộc NO-079 của người điều phối — hiện dòng NO-079 chưa ghi các tên nhánh thêm (#7).

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | R-17 · LOG-02 | `upload_prefix_of` là hàm **công khai** của lõi, docstring gọi đầu vào là "khoá không tin trong payload ML", nhưng chỉ kiểm phần đầu: khoá có đuôi `../../../../x` hay `pages//0.png` vẫn ra tiền tố hợp lệ, không lỗi (**probe P4**). Người gọi duy nhất hiện nay (`InferStepPayload._consistent`) an toàn vì `page_key` là `ObjectKey` (đã qua `check_key` trước `model_validator`), nên **không có lỗi đang chạy**; nhưng bản cũ là hàm riêng `_upload_prefix`, nay là API lõi mà NO-079 đang hướng B2-04 tới ("lọc khoá bằng hàm của `storage.keys`/lõi") — người gọi sau đọc docstring sẽ tin khoá trả về đã được kiểm | `packages/core/object_keys.py:74-85` | Thêm `check_key(key)` ở dòng đầu (fail-closed, một dòng, không đổi hành vi của payload) kèm một ca `…/../x` trong `test_upload_prefix_of_rejects`; hoặc ghi rõ điều kiện trước trong docstring ("`key` phải đã qua `check_key`") |
| 2 | Nit | LOG-02 · MNT-04 | Id được kiểm (tầng trước) **trước** chữ của bố cục, nên khoá không thuộc lượt tải lên nào nhận thông báo sai trường: `ml/models/mdl_…/a/b/c/d.onnx` → "id tầng sai mẫu …: 'a'" (**probe P4**). Chỉ là chẩn đoán (`define_task` chỉ ghi số lỗi) | `packages/core/object_keys.py:80-85` | Bọc lỗi id: `except ValueError as exc: raise ValueError(f"khoá không nằm dưới một lượt tải lên: {key!r}") from exc` (trường sai vẫn còn ở `__cause__`), sửa ba ca `match` của `test_upload_prefix_of_rejects`; hoặc giữ nguyên |
| 3 | Nit | TEST-02 | `test_avatar_name_follows_ulid_rule_of_core` vá tên riêng `ids._ULID_RE` với `raising=False` — cần cho lượt đỏ trên `ids.py` cũ (chưa có tên này), nay thừa: đổi tên `_ULID_RE` thì test đỏ với "DID NOT RAISE" thay vì `AttributeError` rõ nguyên nhân | `packages/storage/tests/test_keys.py:37-42` | Bỏ `raising=False`; hoặc thay bằng `assert keys.is_ulid is ids.is_ulid` (cùng lối `test_key_rules_come_from_core`) — core đã chốt `is_id` đọc `is_ulid` |
| 4 | Nit | R-01 | Ba hàm test mới thiếu docstring (đúng thói của hai file: 12 + 1 hàm cũ cũng thiếu) | `packages/core/tests/test_ids.py:105`, `:116`; `packages/core/tests/test_object_keys.py:121` | Một câu mỗi hàm |
| 5 | Nit | R-07 | `ml_contracts._id_of.check` nhắc lại `check_id` (cùng thông báo, bỏ giá trị). Lý do tác giả giữ ("cố ý không lặp giá trị không tin") không đứng: `define_task` chỉ ghi `exc.error_count()` (`packages/messaging/tasks.py:202-203`), và chính payload này nay đã lặp đoạn id qua `upload_prefix_of → check_id` (probe P4) | `packages/ml_contracts/payloads.py:37-46` | `return AfterValidator(functools.partial(check_id, prefix))` ở lượt NO-081; ngoài phạm vi [4]/luật 3 của FIX-058 nên không đòi trong nhánh này |
| 6 | Nit | R-07 | Bảng chữ Crockford vẫn viết hai lần trong cùng file — `_CROCKFORD` (mã hoá ở `new_id`) và lớp ký tự của `_ULID_RE` (kiểm ở `is_ulid`) — trong khi docstring `is_ulid` nói "nguồn duy nhất của luật thân ULID". Cặp có từ trước; dòng 35 do nhánh sửa | `packages/core/ids.py:34-35`, `:58` | `_ULID_RE = re.compile(f"[{_CROCKFORD}]{{26}}")` |
| 7 | P3 | R-34 (sổ) | Nhánh thêm năm tên công khai vào lõi dùng chung — `project_prefix`, `upload_prefix`, `upload_prefix_of` (`object_keys.py`), `is_ulid`, `check_id` (`ids.py`) — báo cáo tác giả nói §2.2 cần dòng cho chúng, nhưng dòng `DEBT.md` NO-079 vẫn chỉ liệt kê `check_key, check_prefix, is_segment, MAX_KEY_BYTES, META_SUFFIX`; báo cáo không phải sổ bền. Cột "Chủ" của NO-081 chỉ ghi B0-04 · B5-01 trong khi hướng chữa đặt mã vào `packages/core/object_keys.py` (B0-02 — như FIX-056 của NO-077) | `DEBT.md:98` (NO-079), `DEBT.md:100` (NO-081) | Người điều phối bổ sung vào NO-079 (nhật ký quản trị, commit thẳng `main` được theo R-36) và thêm "B0-02 (`packages/core/object_keys.py`)" vào cột chủ của NO-081 — văn bản đề xuất ở mục Sổ nợ |

**P0: 0 · P1: 0 · P2: 0 · P3: 2 · Nit: 5**

## Những chỗ đã soi kỹ và **đạt**

- **Sửa gốc (R-19), mỗi FIX:** FIX-054 — `is_id` kiểm thân **qua** `is_ulid` (đột biến `ids.is_ulid` → `is_id` sai, test chốt); FIX-055 — `avatar` gọi `is_ulid`, `_ULID_RE` của `storage` bị xoá; FIX-056 — bố cục `projects/{prj}/floors/{L-…}/uploads/{upl}/` chỉ còn **một** chuỗi dựng (`object_keys.py:59`, `:71`), `upload_prefix_of` tách bằng **dựng lại** (P2 M1 chứng minh vế so từng byte có test); FIX-057 — `storage.keys.project_prefix`/`upload_prefix` **là** hàm lõi (`is`), `_entity_id`/`_level_id` bị xoá, mọi hàm dựng của `storage` (và qua `upload_page`, cả `server_chosen_kind`) đi qua lõi; FIX-058 — `_upload_prefix` bị xoá, `InferStepPayload` gọi `upload_prefix_of`. Không còn bản dựng/tách thứ hai của tiền tố lượt tải lên trong mã sản phẩm (grep `projects/`, `/uploads/`: chỉ `object_keys.py`). Phần lặp còn lại đúng là NO-081.
- **Thông báo lỗi nêu đúng trường như test storage đòi:** `check_id` giữ nguyên văn thông báo của `_entity_id` cũ (`id phải có dạng {prefix}_<ULID>: …` → khớp `prj_`, `upl_`, `run_`, `mdl_`, `dsv_`), tầng giữ nguyên văn `_level_id` cũ (`id tầng sai mẫu L-<base36 HOA>: …`); `test_builders_reject_wrong_ids` của storage (16 ca) xanh không sửa; core có bản riêng (`test_upload_prefix_rejects_wrong_ids`, 5 ca, gồm tầng dài 9).
- **Hành vi không đổi:** P3 — `is_id` lệch 0/400 009, bộ tách lệch 0/180 000 về nhận/từ chối và tiền tố; chỉ thông báo lỗi payload đổi (có lợi: nêu trường), không ai khớp chuỗi đó. `upload_prefix` giữ thứ tự kiểm cũ (tầng → dự án → lượt tải lên) nên `storage` ném đúng lỗi như trước.
- **Tiền tố luôn kết thúc bằng `/`** (qua `check_prefix`), `upload_prefix` nằm dưới `project_prefix` — dọn rác dự án (`delete_prefix(keys.project_prefix(…))`, test S3/LocalDisk/hợp đồng) vẫn phủ mọi lượt tải lên.
- **Test một nguồn đúng [6]:** mỗi FIX có test đột biến/`is` đỏ trên mã cũ (P1) — không test nào chỉ kiểm giá trị trùng khít (thứ hai bản sao cũng qua). Test cũ duy nhất bị sửa (`test_server_chosen_kind_reads_id_rules_of_core`) đổi **đích** đột biến theo nơi luật nay sống (`object_keys.is_spatial_id`, `ids.is_id`) và thêm một ca — chặt hơn, không nới (FIX.md luật 2); tác giả khai ở "Lệch khỏi prompt".
- **Không mock dịch vụ, không đồng hồ thật:** bốn file test là test thuần; `monkeypatch` chỉ vá luật thuần để chốt một nguồn.
- **NO-081 đúng sự thật:** sáu vị trí dòng khớp HEAD (`storage/keys.py:63` `runs/{run}/{step}/` trong `run_artifact`, `:75` `ml/models/{mdl}/` trong `model_artifact`; `payloads.py:132` `…runs/{run_id}/{step}/`, `:26` `MODELS_PREFIX`, dùng ở `:110`, `:297`). Grep toàn `packages/`, `apps/` không còn bản bố cục thứ hai nào khác trong mã sản phẩm (`ml_contracts/datasets.py` chỉ dựng đường **tương đối** dưới `ml/datasets/{dsv}/`, không dựng lại tiền tố). Mức P3, chủ B0-04 · B5-01 đúng — thiếu B0-02 (#7).

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | Dời thêm `project_prefix` và thêm `check_id` (ngoài "chỉ tiền tố lượt tải lên"); đã dừng và `ask`, người điều phối chọn phương án A, `check_id` ở `ids.py` | **Đứng được.** Dời riêng `upload_prefix` sẽ để `projects/{prj}/` và thông báo id có hai nguồn — đúng lỗi NO-077 đang chữa. Làm đúng điều [5] ("… dừng và `ask`") |
| 2 | Sửa `test_server_chosen_kind_reads_id_rules_of_core` (đổi đích đột biến, thêm một ca) | **Đứng được** — xem mục "đạt"; P1 FIX-057 cho thấy bản sửa đỏ trên `keys.py` cũ |
| 3 | `--amend` commit FIX-054 (RUF001, `chr(0xFF10)`) trước khi có commit sau | **Đứng được** — chưa đẩy, cùng ngữ nghĩa; P1 FIX-054 tự chạy lại trên bản sau amend |
| 4 | `--amend` thông điệp commit gộp `main` | **Đứng được** — BE-00 §13.2; trailer đọc được |
| 5 | Giữ `ml_contracts._id_of` tự ném lỗi thay vì gọi `check_id` "vì không lặp giá trị không tin" | **Giữ nguyên là đúng phạm vi** (FIX.md luật 3), nhưng **lý do không đứng** — Nit #5 |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Nợ nhánh đóng nói đúng sự thật | đạt — NO-076, NO-077 `✅` kèm ngày đóng; mọi con số đỏ/xanh trong dòng khớp probe P1 (14/1/27/4/1) |
| Mọi nợ tác giả nêu đều có dòng | đạt một phần — NO-081 `⬜` P3 có dòng, đúng sự thật; phần mở rộng NO-079 (tên mới của lõi) chỉ nằm trong báo cáo → #7 |
| Nợ P0/P1 còn `⬜`/`🔧` do nhánh này | không |
| Nợ do review này chỉ ra đã có dòng | **chưa** — xem dưới (phiên này **không** tự ghi `DEBT.md`) |

Dòng đề xuất (id do người điều phối cấp):

- Nếu #1 không sửa trong nhánh: `| ⬜ | NO-<nnn> | 2026-09-22 | | \`packages/core/object_keys.py:74\` \`upload_prefix_of\` (hàm công khai, docstring "khoá không tin") chỉ kiểm phần đầu: khoá có đuôi \`../x\` hay \`//\` vẫn ra tiền tố, không lỗi (probe review: \`…/uploads/{upl}/../../../../x\` → tiền tố) | Tách từ \`_upload_prefix\` riêng của \`ml_contracts\` (người gọi đã qua \`ObjectKey\`) thành API lõi mà không thêm điều kiện trước | B0-02 (\`packages/core/object_keys.py\`) | P3 | mở — review merge 2026-09-22 \`fix/b0-04-key-layout-debts\` finding #1. Chữa: \`check_key(key)\` ở dòng đầu + ca \`…/../x\` trong \`test_upload_prefix_of_rejects\`; hoặc docstring ghi rõ "\`key\` phải đã qua \`check_key\`" |`
- Bổ sung vào cuối cột trạng thái của **NO-079**: `· Mở rộng 2026-09-22 (review merge \`fix/b0-04-key-layout-debts\` finding #7): FIX-054/056 thêm vào lõi dùng chung \`packages/core/object_keys.py\` \`project_prefix\`, \`upload_prefix\`, \`upload_prefix_of\` và \`packages/core/ids.py\` \`is_ulid\`, \`check_id\` — dòng §2.2 cần ghi cả năm tên (chủ B0-02 · gọi: B0-04, B5-01) và luật đặt: lõi giữ phần bố cục mà gói không được nhập \`storage\` phải kiểm, hàm dựng khoá ở \`storage\``
- Cột "Chủ" của **NO-081**: thêm `B0-02 (\`packages/core/object_keys.py\`)` trước `B0-04`.
- Nit #2–#6: tác giả tự quyết, không cần dòng; #5 nên gộp vào lượt chữa NO-081.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 (P3 #1; Nit #2) | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 (không đổi HTTP, schema, payload; chỉ thông báo lỗi nội bộ) | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit #3, #4) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 (P3 #7; Nit #5, #6) | 0,12 |

Tổng: 1,25 + 0,75 + 0,60 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,12 = **4,82 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt chạy độc lập (mã thoát từ shell bọc và `docker wait` trùng nhau), `2089 passed, 0 failed, 10 skipped` (10 skip hợp lệ), độ phủ đạt ở mọi gói bị chạm (`packages/core` 100 % / 100 %, `packages/storage` 99,64 % / 98,28 %, `packages/ml_contracts` 99,90 % / 99,56 %; tập file bị chạm 100 % / 100 %), không có P0/P1/P2, điểm 4,82 ≥ 4,0. Cả năm FIX sửa đúng gốc và đúng phạm vi [4] (ngoại lệ `check_id` đã được duyệt): luật thân ULID và bố cục tiền tố dự án/lượt tải lên mỗi thứ còn một nguồn, `storage` và `ml_contracts` cùng gọi lõi; đỏ trước/xanh sau tự tái hiện đủ 14/1/27/4/1 ca đúng như dòng `DEBT.md`; hành vi nhận/từ chối không đổi trên 580 000 mẫu; không người gọi nào vỡ. Ranh giới mới của `packages/core` đứng được (luật thuần dùng chung, không I/O, `core-isolated` KEPT), với điều kiện sổ NO-079 ghi lại tên mới và luật đặt.

Điều kiện cho phiên merge:

1. **Xung đột `DEBT.md` với `main` @ `8994352`** (duy nhất, `git merge-tree`): lấy dòng `✅` NO-076, NO-077 của nhánh; giữ NO-078, NO-079, NO-080, NO-082..NO-086 của `main`; chèn NO-081 của nhánh giữa NO-080 và NO-082. Không file mã nào xung đột; `main` từ `334d73c` chỉ đổi `apps/api/auth/tests/test_refresh.py` ngoài sổ, không giao với vùng nhánh — lượt verify tích hợp thường lệ sau gộp là đủ.
2. **Trước khi merge** (R-38): ghi các dòng ở mục Sổ nợ — bổ sung NO-079 và cột chủ NO-081 (#7); dòng `⬜` P3 cho #1 nếu tác giả không sửa trong nhánh. Nit #2–#6 không chặn merge.
3. Gộp bằng `git merge --no-ff` (R-36: nhánh mang trailer của B0-02, B0-04 **và** B5-01 cùng `Fix: FIX-054..058`), **không** squash.
4. Điền sha vào cột "Commit" của `docs/fixes.md`: FIX-054 `b2864d9`, FIX-055 `5c8586a`, FIX-056 `271382b`, FIX-057 `318dc5b`, FIX-058 `778c052` (`--no-ff` giữ nguyên các sha này).
