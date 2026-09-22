# Review merge fix/b0-03-check-constraint-names → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả; mọi khẳng định trong commit, `DEBT.md` và báo cáo `W4-DB.report.md` đều tự kiểm lại) · Commit đầu nhánh: `593bcea54b77`. Merge-base `afa29ed`; 3 commit: `f37c52e` B0-01 + FIX-038, `4e8e2a5` B0-06 + FIX-037, `593bcea` B0-03 + FIX-036. Từ lúc giao việc, `main` đã đi tới `55333dc` (thêm `1021267`, `9597669`, `567caa8`, `25dad10` là tài liệu, và `55333dc` B5-01 `packages/ml_contracts`, `apps/ml`). Không commit nào trên `main` đụng `packages/db`, `packages/testing`, `tools/` hay migration. `git merge-tree main HEAD` chỉ xung đột ở **`DEBT.md`** (xem "Hợp nhất với `main`").
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**. Tôi chạy tại chỗ trong worktree sạch của nhánh lúc 2026-09-22T02:20:58Z, lúc đó `docker ps --filter name=verify-run` = 1. Mã thoát lấy thẳng từ shell bọc (shell không bị cắt). Log ở `C:/Users/mxuan/AppData/Local/Temp/claude/C--Users-mxuan-orca-workspaces-appback-fix-db/b117aab8-86fc-4dfa-a556-f730ac0f12f8/scratchpad/verify.log`. Kết quả: `1644 passed, 0 failed, 10 skipped` trong 330,1 s. Cả 10 skip nằm ở `apps/api/core/tests/test_common.py`: tập tham số rỗng vì chưa có route được bảo vệ, đúng ngoại lệ BE-00 §12 như các lượt review trước.
- Độ phủ (in từ `tools.coverage_gate` của lượt trên, không lấy từ báo cáo tác giả):
  - tổng: dòng **99,19 %** · nhánh **96,62 %**
  - `packages/db`: dòng **98,80 %** · nhánh **97,32 %** · `tools`: dòng **98,66 %** · nhánh **94,93 %**
  - tập file bị chạm: dòng **98,26 %** · nhánh **96,27 %**
  - Tổng lệch 0,02–0,06 điểm so với báo cáo tác giả (99,21 / 96,68). Đó là sai số đo của `coverage` quanh `await` đi qua greenlet (NO-035). Không có dòng mới nào của nhánh mà coverage báo thiếu.

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (266 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (232 file) |
| 4 | `lint-imports` | đạt (mọi hợp đồng KEPT) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf` bị chạm; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5) |
| 6 | `lint_migrations` → `migrate_check` | đạt (4 revision; 10/10 bước con, gồm "model khớp DB" và bước mới "tên CHECK khớp model") |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt: Smoke, H1 186 mẫu. H3/H4/H5 `không áp dụng` là **hợp lệ** vì B1-02, B3-05, B4-01 chưa hợp nhất |
| 8 | openapi | đạt (nhánh worker: xuất được) |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (lúc đầu phiên và lúc cuối phiên, sau khi xoá file probe) |
| `changes/<mã>.md` của B0-01, B0-03, B0-06 | đạt: cả ba đã có trên `main`. Nhánh chỉ mang FIX, không bàn giao prompt mới |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt: 67, 69, 65 ký tự |
| Trailer đọc được (R-36b) | đạt. `%(trailers:key=Prompt)` in đúng `B0-01` / `B0-06` / `B0-03`, `Fix:` in đúng `FIX-038` / `FIX-037` / `FIX-036`. Khối trailer liền nhau, có dòng trống ngay trước |
| Đụng `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/verify/*` | không |
| `docs/contracts.toml` (file của người điều phối) | có sửa, nhưng **đã được phép**: đoạn "Giao việc FIX-032..FIX-037" cho FIX-037 thêm đúng tên revision của nó. Diff chỉ có `revisions = ["r20260921_b0_06_fix037"]` |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không có dòng thêm nào như vậy |

File ngoài cột "Sở hữu" của B0-03 là `tools/lint_migrations.py` và `tools/tests/test_lint_migrations_main.py` (B0-01, FIX-038). Việc sửa hai file này được phép theo `reply-w4.txt`, trong đúng danh sách file cho phép ở đó. Không có điều kiện dừng sớm nào kích hoạt.

## Công cụ kiểm tại chỗ

Probe chạy bằng `bash tools/verify/run.sh shell < script.sh`, trên bản sao `/tmp/w` trong container, với `PYTHONPATH=/tmp/w` và `pytest -p no:cacheprovider -o addopts=`. Bản file của `main` được đặt tạm dưới `.cache/rv/` (đã git-ignore) rồi `cp` đè bên trong container. `.cache/rv/` đã xoá sau khi chạy.

- **P1: FIX-038, đỏ trước / xanh sau.**
  - `lint_migrations.py` của `main` + test của nhánh (`tools/tests/test_lint_migrations{,_main}.py`): **2 failed, 30 passed**. Hai test đỏ là `test_contract_đã_đăng_ký_được_phá_huỷ` và `…_vẫn_kiểm_luật_không_phá_huỷ`.
  - Bản của nhánh: **32 passed**.
  - Lint của `main` chạy trên `versions/` của nhánh thoát **1**: hai lần `[execute chuỗi SQL cấm] ALTER TABLE idempotency_records RENAME CONSTRAINT …` ở `r20260921_b0_06_fix037`. Nghĩa là không có FIX-038 thì FIX-037 không vào được. Lint của nhánh thoát **0** (4 revision).
  - Test của `main` chạy trên lint của nhánh: **29 passed**, không hồi quy.
- **P2: phạm vi miễn trừ của FIX-038 so với `reply-w4.txt`.** Tôi dựng từng revision tạm rồi gọi `lint_migrations.run`.
  - (a) Tên đã đăng ký nhưng **không** có dòng `# contract:`, thân có `RENAME`: vẫn báo `execute chuỗi SQL cấm`.
  - (b) `# contract:` nằm ở dòng 11, thân có `drop_column`: vẫn báo `thao tác cấm`.
  - (c) Contract đã đăng ký, `create_index(..., postgresql_concurrently=True)` ngoài `autocommit_block`: vẫn báo lỗi.
  - (d) Contract đã đăng ký, SQL viết bằng f-string: vẫn báo "không phải hằng chuỗi".
  - (e) Contract đã đăng ký, `sa.text(biến)`: vẫn báo cả hai luật "không phải hằng chuỗi".
  - (f) Contract đã đăng ký, thân có `rename_table`, `drop_table`, `alter_column(type_=…)`, `alter_column(new_column_name=…)`, `TRUNCATE`, `DELETE FROM`: **không** báo gì, đúng danh sách miễn.
  - (g) Chưa đăng ký, thân có `drop_column`: báo cả `# contract: chưa đăng ký` lẫn `thao tác cấm`.
  - Kết luận: miễn trừ **đúng** phạm vi người điều phối cho phép, không rộng hơn. `batch_alter_table` vẫn đi thẳng vào `report` (`lint_migrations.py:185`), và bài kiểm tên revision chạy trước `_lint_body`, không đổi.
- **P3: FIX-036, đỏ trước / xanh sau.**
  - `migrate_check.py` của `main` + test của nhánh, `-k check_name`: **2 failed**. Thông báo lỗi: `assert 'model khớp DB' == 'tên CHECK khớp model'` và `assert [] == ['tên CHECK khớp model']`.
  - Bản của nhánh: `test_migrate_check.py` **12 passed**.
- **P4: bước 6 theo spec [6] của FIX-036/037.**
  - `migrate_check` của `main`, **không** có revision FIX-037: thoát **0**, 9/9. Đây chính là "xanh giả" mà NO-057 mô tả.
  - `migrate_check` của nhánh, không có FIX-037: thoát **1**. Bước `tên CHECK khớp model hỏng — CHECK thừa trong DB: ['ck_idempotency_records_ck_idempotency_records_key_format', 'ck_idempotency_records_ck_idempotency_records_state']; thiếu trong DB: ['ck_idempotency_records_key_format', 'ck_idempotency_records_state']`.
  - Có cả FIX-037: thoát **0**, 10/10. `downgrade -1` đã chạy chính `downgrade()` của FIX-037 trên DB có dữ liệu seed, rồi `upgrade head` lại.
- **P5: biên của `_check_name_drift`.** Tôi dùng `postgres:16-alpine` thật và `metadata.create_all`.
  - Tên CHECK dựng theo quy ước dài hơn 63 ký tự: DB có `ck_t_long_xxx…_d188`, kết quả drift là `''`. Khẳng định "đúng cách cắt tên như DDL" trong docstring là **đúng**.
  - `CHECK` của domain `information_schema` (`cardinal_number_domain_check`, `yes_or_no_check`, có `conrelid = 0`) bị loại **đúng**.
  - `Boolean(create_constraint=True)`: hàm **ném** `InvalidRequestError('Naming convention including %(constraint_name)s token requires that constraint is explicitly named.')`.
  - `Enum("a", "b", name="kind", create_constraint=True)` (enum native): drift báo `thiếu trong DB: ['ck_t_enum_kind']`, trong khi DDL của chính model không bao giờ tạo CHECK đó (xem #2).
- **P6: khoá của `RENAME CONSTRAINT`.** Trong giao dịch, `ALTER TABLE r RENAME CONSTRAINT …` giữ `AccessExclusiveLock` trên bảng. Thời gian chờ khoá có trần: `env.py:47` đặt `lock_timeout = db_lock_timeout_ms` cho mọi lượt Alembic. Lệnh chỉ sửa catalog, không quét dữ liệu. Không có finding.
- **P7: độ phức tạp** (`ruff --isolated --select C901,PLR0912,PLR0915`, cộng đếm dòng bằng AST):
  - `_lint_body`: `main` 69 dòng, CC 28, 25 nhánh, 53 lệnh. Nhánh: 78 dòng, CC 28, 25 nhánh, 55 lệnh.
  - `run_checks`: `main` 77 dòng, CC 12. Nhánh: 82 dòng, CC 13.
  - `_check_name_drift` (mới): 20 dòng, không vượt ngưỡng nào (xem #1).

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | MNT-01 · R-08 | Hai hàm mà nhánh sửa **đã vượt** R-08 từ trên `main`, và nhánh làm cả hai dài thêm. Probe P7: `_lint_body` từ 69 lên 78 dòng, CC 28, 25 nhánh, 55 lệnh. `run_checks` từ 77 lên 82 dòng, CC từ 12 lên 13. Nhánh **không tạo ra** lỗi này: dòng logic thêm vào chỉ gồm một biến `destructive`, một biểu thức chọn báo cáo, và một closure không rẽ nhánh. Tách hàm trong FIX này là mở rộng phạm vi (FIX.md luật 3), nên đúng là không làm ở đây | `tools/lint_migrations.py:150-227`; `packages/db/migrate_check.py:107-188` | Ghi `DEBT.md`, hai chủ. `_lint_body` tách mỗi luật thành một hàm `_check_<luật>(node, …)`, gộp cùng #4. `run_checks` đưa các closure bước lên mức module, nhận `engine`/`config` qua tham số |
| 2 | P3 | LOG-02 · R-05 | `_check_name_drift` lấy **mọi** `CheckConstraint` của bảng, kể cả CHECK gắn với kiểu (`Boolean`/`Enum` có `create_constraint=True`). DDL trên Postgres bỏ qua các CHECK này qua `_create_rule` (kiểu native). Probe P5: `Boolean(create_constraint=True)` làm bước **ném** `InvalidRequestError`, còn `Enum(…, create_constraint=True)` làm bước báo `thiếu trong DB: ['ck_t_enum_kind']`. Cả hai là đỏ giả (fail-closed, không xanh giả). Hôm nay chưa ai dùng: `grep create_constraint\|Enum(` trong `packages/`, `apps/` không có kết quả. Nhưng prompt sau khai kiểu đó sẽ bị chặn ở bước 6 mà không được sửa file của B0-03 | `packages/db/migrate_check.py:97-100` | Bỏ các ràng buộc có `_create_rule` trả `False` với DDL compiler của dialect. Cách này dùng API riêng của SQLAlchemy, nên cần comment ghi ngưỡng theo R-05. Tối thiểu: thêm giới hạn này vào docstring, kèm một test chốt hành vi |
| 3 | P3 | API-04 (tài liệu) | Hiến chương chưa theo kịp hai FIX. BE-00 §6.1 "Vòng kiểm" dừng ở "→ model khớp DB", chưa có bước 10 "tên CHECK khớp model" (FIX-036). Gạch "Revision contract" chưa nói revision đã đăng ký được miễn những luật nào (FIX-038). §12 dòng 6 cũng chỉ liệt kê tới `upgrade head; đúng 1 head`. Tác giả đã nêu điều này trong báo cáo và đúng là không sửa (hiến chương là file của người điều phối) | `docs/charter/BE-00.md:299-300`, `:464` | Người điều phối sửa BE-00 §6.1, §12 sau khi gộp. Ghi `DEBT.md`, dòng đề xuất ở dưới |
| 4 | Nit | MNT-04 | Phân loại "luật phá huỷ hay không" bị giấu trong vòng lặp. Có một `Report()` dùng để bỏ đi, và một biểu thức `(report if attr == "batch_alter_table" else destructive)`, vì `_BANNED_CALL_NAMES` trộn bốn thao tác phá huỷ với `batch_alter_table`. Đúng hành vi (P2), nhưng người sau thêm một tên vào tập đó sẽ không biết mình vừa miễn nó cho contract | `tools/lint_migrations.py:23`, `:159`, `:185` | Khai riêng hai hằng, `_DESTRUCTIVE_CALL_NAMES = {"drop_table", "drop_column", "drop_constraint", "rename_table"}` và `batch_alter_table`. Thay `Report()` bỏ đi bằng `if not contract:`. Làm cùng lượt tách hàm ở #1 |
| 5 | Nit | R-07 · R-11 | Test của B1-01 `test_check_constraint_names_match_the_model` nay trùng bất biến với bước 10 của `migrate_check`: cùng đọc `pg_constraint`, cùng so với tên model. Nó còn hẹp hơn (chỉ `users`/`refresh_sessions`, chỉ CHECK mức bảng). File thuộc B1-01 nên nhánh này không được xoá (K27) | `apps/api/auth/tests/test_units.py:199-214` | B1-01 xoá test này ở lần sửa kế tiếp. Không cần dòng `DEBT.md` riêng |
| 6 | Nit | — (sổ) | Spec FIX-037 [5] vẫn ghi `r20260922_b0_06_fix037`. Tên thật là `r20260921_b0_06_fix037`: `new_revision` lấy ngày UTC, đứng được. Cột "Commit" của FIX-036..038 vẫn ghi tên nhánh | `docs/fixes.md:45-47`, `:335` (trên `main`) | Người điều phối sửa tên trong spec, rồi điền `593bcea` (FIX-036), `4e8e2a5` (FIX-037), `f37c52e` (FIX-038) khi gộp. `--no-ff` giữ nguyên các sha này |

**P0: 0 · P1: 0 · P2: 0 · P3: 3 · Nit: 3**

## Những chỗ đã soi kỹ và **đạt**

- **FIX-036 sửa đúng gốc (R-19).** Lỗ nằm ở cổng, không ở một revision. `compare_metadata` không bao giờ so CHECK, nên mọi revision về sau truyền tên đủ tiền tố mà không bọc `op.f(...)` đều lọt. Bước mới so **mọi** bảng của `Base.metadata` (`load_all_models()` chạy trước), gồm cả CHECK khai trong `Column(...)`, nằm ở `column.constraints`, mà test của B1-01 (#5) bỏ sót. Tên model dựng bằng `format_constraint` của dialect: cùng quy ước, cùng cách cắt tên ở 63 ký tự như DDL (P5). Phía DB là **một** truy vấn có tham số ràng buộc (`:tables` ép kiểu `text[]`, không nối chuỗi), lọc `contype = 'c'` và `conrelid` thuộc bảng của metadata, nên CHECK của domain và của bảng ngoài model không bị xét. Bước đặt **sau** "model khớp DB", nên bảng thiếu đã hỏng ở bước trước. Thông báo lỗi in cả tên thừa lẫn tên thiếu, đủ để sửa mà không phải đoán. Đúng [5] của spec.
- **FIX-037.**
  - Revision contract được tạo bằng `new_revision` (dài 22 ký tự ≤ 32, tên file đúng mẫu `r<ngày>_<mã>_fix<nnn>_<việc>.py`). Có `# contract:` ở dòng 1, tên có trong `docs/contracts.toml`, `down_revision` là head hiện tại `r20260921_b1_01`, nên cả nhánh lẫn `main` + nhánh chỉ có **1 head**.
  - Mỗi FIX có đúng một revision. `upgrade()` và `downgrade()` là hai cặp `RENAME CONSTRAINT` viết bằng hằng chuỗi, đường lùi đã chạy thật (P4).
  - Revision đã hợp nhất (`r20260920_b0_06_idempotency.py`) **không** bị sửa.
  - Tương thích ngược (DB-01): không mã nào tham chiếu tên CHECK (`grep` toàn repo chỉ ra chính revision). `packages/db/errors.py:73` chỉ đọc tên của vi phạm **unique**. Rolling deploy với mã cũ không đổi hành vi.
  - Khoá (DB-02): `AccessExclusiveLock` chỉ trên catalog, chờ có trần nhờ `lock_timeout` của `env.py` (P6).
- **FIX-038.**
  - Sửa ở chỗ mọi revision đều đi qua (`_lint_file` → `_lint_body`), không vá riêng file của FIX-037.
  - Điều kiện miễn đòi **cả** dòng `# contract:` trong 10 dòng đầu **lẫn** tên đã đăng ký (P2 a, b).
  - Ba test mới đúng yêu cầu của `reply-w4.txt`. Test "chưa đăng ký có `RENAME` → hỏng" là test chặn hồi quy, xanh cả trước lẫn sau, đúng như tác giả nói. Test cũ `test_contract_đã_đăng_ký_đạt` được giữ lại qua helper `_contract`.
- **Thứ tự commit** FIX-038 → FIX-037 → FIX-036 đúng chỉ định. Theo cấu trúc, không commit trung gian nào có bước 6 đỏ vì tên CHECK: FIX-036 (bước so tên) đến sau cùng, còn FIX-037 đi sau FIX-038 (lint cho qua). Đây là suy luận từ P1 và P4, tôi không chạy verify riêng cho từng commit. Mỗi dòng `DEBT.md` chuyển `✅` trong chính commit sửa: NO-058 ở `f37c52e`; NO-057 ở `593bcea`, là commit cuối trong hai FIX của nó.
- **Test** chạy Postgres thật (K23), có negative case, đỏ trước / xanh sau đã tự tái hiện (P1, P3). Hai test đếm bước (`len(results) == 10`, `out.count("đạt") == 11`) chỉ đổi con số theo bước mới, không nới assert.
- **Docstring** (R-01, R-02): `_check_name_drift` và `_lint_body` có docstring nói lý do và cạm bẫy (vì sao `compare_metadata` không đủ, vì sao CHECK mức cột ở chỗ khác, vì sao SQL không hằng vẫn bị chặn trong contract), không kể lại mã. Hàm mới 20 dòng.
- **MNT-05:** khoảng 60 dòng logic sản phẩm và khoảng 90 dòng test, dưới trần 400.

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | Revision tên `r20260921_b0_06_fix037`, không phải `r20260922_…` như spec | **Đứng được.** BE-00 §6.1 bắt tạo revision bằng `new_revision`, và công cụ đó lấy ngày UTC. `docs/contracts.toml` có đúng tên thật. Người điều phối sửa spec (#6) |
| 2 | Thêm FIX-038 (B0-01) ngoài [4] ban đầu | **Đứng được.** Người điều phối đã duyệt qua `ask` (`reply-w4.txt`, phương án A, miễn trừ hẹp). Mã khớp **đúng** phạm vi đó (P2). Row và spec FIX-038 đã có trên `main` (`docs/fixes.md`) |
| 3 | Số bước con của `migrate_check` từ 9 lên 10; hai test đếm bước đổi số | **Đứng được.** Chỉ đổi con số, không nới assert |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Mọi nợ tác giả nêu đều có dòng | đạt. NO-057 `✅` (FIX-036, FIX-037) và NO-058 `✅` (FIX-038) có ngày đóng và mã FIX. Mọi câu trong cột trạng thái (đỏ 2/2 và 2/32 trước; bước 6 chỉ có FIX-036 hỏng đúng hai tên; có cả FIX-037 thì đạt) **khớp** probe P1–P4 |
| Nợ P0/P1 còn `⬜`/`🔧` do nhánh để lại | không |
| **Mức của NO-058** (`main` ghi `🔧 P3`, nhánh ghi `✅ P2`) | **P2 đúng** theo `RULE.md` §1. Lint trái với hiến chương: BE-00 §6.1 định nghĩa đường revision contract, còn lint làm đường đó **không dùng được**. Đây là "vi phạm contract nội bộ", ảnh hưởng vận hành (chặn mọi revision contract, kể cả việc sửa NO-057), không phải style hay đặt tên (P3). Không lên P1 vì lỗi fail-closed: nó chặn nhầm chứ không để lọt, và không liên quan tải, race hay khoá bảng. Lúc gộp giữ dòng của nhánh |
| Nợ do review này chỉ ra đã có dòng | **chưa**, xem dưới |

Dòng đề xuất (người điều phối cấp id; phiên này **không** tự ghi vào `DEBT.md`):

- `| ⬜ | NO-<nnn> | 2026-09-22 | | tools/lint_migrations.py:_lint_body vượt R-08: 78 dòng, CC 28, 25 nhánh, 55 lệnh (trên main 69 dòng, CC 28); FIX-038 thêm 9 dòng | Mọi luật của BE-00 §6.1 viết nối tiếp trong một vòng lặp qua node | B0-01 (tools/lint_migrations.py) | P3 | mở — review merge 2026-09-22 fix/b0-03-check-constraint-names finding #1. Chữa: mỗi luật một hàm _check_<luật>(node, …); tách _DESTRUCTIVE_CALL_NAMES khỏi batch_alter_table, bỏ Report() dùng một lần (finding #4) |`
- `| ⬜ | NO-<nnn> | 2026-09-22 | | packages/db/migrate_check.py:run_checks vượt R-08: 82 dòng, CC 13 (trên main 77 dòng, CC 12); FIX-036 thêm một closure bước | Mười bước khai thành closure lồng trong run_checks | B0-03 (packages/db/migrate_check.py) | P3 | mở — review merge 2026-09-22 fix/b0-03-check-constraint-names finding #1. Chữa: đưa các bước lên mức module, nhận engine/config/target qua tham số; run_checks chỉ còn vòng lặp và dọn engine |`
- `| ⬜ | NO-<nnn> | 2026-09-22 | | Bước "tên CHECK khớp model" của migrate_check đỏ giả với CHECK gắn kiểu mà DDL Postgres bỏ qua: Boolean(create_constraint=True) làm bước ném InvalidRequestError, Enum(…, create_constraint=True) native làm bước báo "thiếu trong DB" | _check_name_drift lấy mọi CheckConstraint của bảng, không xét _create_rule của dialect | B0-03 (packages/db/migrate_check.py) | P3 | mở — review merge 2026-09-22 finding #2, probe trên postgres:16-alpine. Chưa model nào dùng (grep create_constraint, Enum( rỗng). Chữa: bỏ ràng buộc có _create_rule trả False với DDL compiler, comment ngưỡng theo R-05; tối thiểu ghi giới hạn vào docstring kèm test chốt |`
- `| ⬜ | NO-<nnn> | 2026-09-22 | | BE-00 §6.1 "Vòng kiểm" chưa có bước "tên CHECK khớp model" (FIX-036); gạch "Revision contract" chưa nói revision đã đăng ký được miễn đúng các luật phá huỷ (FIX-038); §12 dòng 6 chưa liệt kê bước mới | Hiến chương viết trước FIX-036, FIX-038 | người điều phối (docs/charter/BE-00.md) | P3 | mở — review merge 2026-09-22 finding #3. Chữa: "… → model khớp DB → tên CHECK khớp model"; thêm vào gạch contract: "miễn drop_*, rename_table, alter_column đổi tên/nullable=False/type_, chuỗi SQL phá huỷ, add_column NOT NULL không default; vẫn kiểm SQL không hằng, batch_alter_table, index khoá bảng, tên revision" |`

## Hợp nhất với `main`

- `git merge-tree --write-tree main HEAD` (với `main` = `55333dc`) chỉ xung đột ở **`DEBT.md`**, trong khối dòng 76–87. `main` có NO-057 `🔧`, NO-058 `🔧 P3` và NO-060…064; nhánh có NO-057 `✅` và NO-058 `✅ P2`. Cách giải: lấy **hai dòng của nhánh** cho NO-057 và NO-058, giữ nguyên NO-060…064 của `main` ngay sau chúng. `docs/fixes.md` và `docs/contracts.toml` không xung đột.
- Người gọi mọi API bị đổi (`git grep` trên `main`):
  - `_lint_body` là hàm riêng, tham số mới là keyword có mặc định, và người gọi duy nhất là `_lint_file`.
  - `run_checks` chỉ có `test_migrate_check.py` gọi, đều đã cập nhật. `tools/verify/steps.py:165` chỉ đọc mã thoát của `python -m packages.db.migrate_check`, không đếm bước. `tools/tests/test_steps_commands.py` giả lập mã thoát.
  - `tools.contract.check.run_checks` là hàm khác, cùng tên.
  - B5-01 (`55333dc`) không có migration và không có model mới, nên bước 10 không nhận thêm bảng nào.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 (P3 #2) | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 4 (P3 #3) | 0,40 |
| TEST – Kiểm thử | 7 % | 5 (Nit #5) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 (P3 #1; Nit #4, #6) | 0,12 |

Tổng: 1,25 + 0,75 + 0,60 + 0,50 + 0,50 + 0,40 + 0,35 + 0,25 + 0,12 = **4,72 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt tôi tự chạy (1644 passed, 0 failed, 10 skipped hợp lệ). Độ phủ đạt ở mọi gói bị chạm: `packages/db` 98,80 % / 97,32 %, `tools` 98,66 % / 94,93 %. Không có P0/P1/P2, điểm 4,72 ≥ 4,0.

Cả ba FIX đã được chứng minh bằng chạy thật chứ không chỉ khẳng định:
- FIX-036 bịt lỗ ở gốc là cổng. Trên `main`, bước 6 xanh giả khi DB mang tên lặp tiền tố. Trên nhánh, bước đó đỏ và in đúng hai tên.
- FIX-037 đưa DB về tên của model bằng một revision contract có đường lùi đã chạy trên DB có dữ liệu, không đụng revision đã hợp nhất, không có người gọi nào phụ thuộc tên cũ.
- FIX-038 miễn **đúng** tập luật phá huỷ mà người điều phối cho phép (7 ca biên của probe P2). Không có nó thì FIX-037 hỏng lint.

Ba P3 đều không do nhánh tạo ra hoặc chưa có người gọi: R-08 có sẵn trên `main`; đỏ giả với CHECK gắn kiểu chưa model nào dùng; hiến chương là file của người điều phối.

Điều kiện cho phiên merge:

1. **Trước khi merge** (R-38): ghi bốn dòng `DEBT.md` đề xuất ở trên (P3 #1 thành hai dòng theo hai chủ, #2, #3). Nit #4–#6 không chặn merge.
2. Gộp bằng `git merge --no-ff` (R-36: nhánh mang trailer của B0-01, B0-06, B0-03 và `Fix: FIX-036/037/038`), **không** squash. Giải xung đột `DEBT.md` như mục "Hợp nhất với `main`": giữ NO-057 `✅` và NO-058 `✅ P2` của nhánh, giữ NO-060…064 của `main`.
3. Người điều phối sửa `docs/fixes.md`: tên revision ở spec FIX-037 [5] thành `r20260921_b0_06_fix037`; cột "Commit" của FIX-036/037/038 thành `593bcea`, `4e8e2a5`, `f37c52e` (#6).
4. Sau khi gộp, chạy verify tích hợp trên `main`. Bước 8 ở nhánh tích hợp so với `openapi.json`, nên xuất nó ra gốc trước (`run.sh openapi`, không commit). Bước 6 phải in 10/10 với 4 revision.
