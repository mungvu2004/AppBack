# Review merge fix/b0-03-migration-tool-debts → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả; mọi khẳng định trong commit, `DEBT.md` và báo cáo `W6-DBTOOLS.report.md` đều tự kiểm lại) · Commit đầu nhánh: `6769d6333cf3`. Merge-base `f5cc758`. 8 commit, trong đó 2 là merge `main` → nhánh: `5ce33f0` B0-03 + FIX-039, `eda31d6` B0-03 + FIX-041, `646740e` B0-03 + FIX-040, `76ec3fd` B0-01 + FIX-042, `135dc42` merge, `3b4f01c` B0-03 + FIX-041 (bổ sung), `e5d0247` merge, `6769d63` B0-03 (dòng NO-080). `main` đã đi tiếp tới **`885a9f1`** (task ghi `311b8c3`; sau đó thêm `885a9f1` mở FIX-052..059, chỉ tài liệu). Các commit mới trên `main` chỉ đụng `packages/core`, `packages/storage`, `packages/ml_contracts`, `docs/`, `DEBT.md`; không đụng `packages/db`, `tools/`, migration. `git merge-tree --write-tree main HEAD` chỉ xung đột ở **`DEBT.md`** (xem "Hợp nhất với `main`").
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**. Tôi chạy tại chỗ trong worktree sạch của nhánh, @ `6769d63`, 2026-09-22T04:35:23Z → 04:40:59Z. Trước khi chạy `docker ps -q --filter name=verify-run | wc -l` = 1 (đã chờ từ 04:34 vì lúc đầu = 2). Mã thoát lấy **thẳng từ shell bọc** (shell không bị cắt). Log giữ hai bản: stdout của `run.sh` ở `C:/Users/mxuan/AppData/Local/Temp/claude/C--Users-mxuan-orca-workspaces-appback-fix-db/a4c2fb3b-a464-46be-ac5d-13d5f6488d79/scratchpad/verify.log`, và `docker logs -f` của container `appback-verify-appback-fix-db-verify-run-d4494b2c8846` chạy song song ở `…/scratchpad/verify.dockerlogs` (phòng NO-080). Bước 5: **`2024 passed, 0 failed, 10 skipped, 1 deselected`** trong 279,1 s. Cả 10 skip nằm ở `apps/api/core/tests/test_common.py` (tập tham số rỗng vì chưa có route được bảo vệ, đúng ngoại lệ BE-00 §12 như các lượt review trước). 1 deselected là `packages/ml_contracts/tests/test_synthetic.py:225` (`@pytest.mark.perf`, bị `addopts = -m "not gpu and not perf"` bỏ ở bước 5 theo thiết kế; bước 5b lo phần `perf`).
- Độ phủ (in từ `tools.coverage_gate` của lượt trên, không lấy từ báo cáo tác giả, vì log của tác giả mất):
  - tổng: dòng **99,35 %** · nhánh **97,52 %**
  - `packages/db`: dòng **98,81 %** · nhánh **97,22 %** · `tools`: dòng **98,68 %** · nhánh **95,64 %**
  - tập file bị chạm: dòng **98,26 %** · nhánh **97,37 %**
  - Chạy riêng `coverage` cho ba file sản phẩm bị sửa (probe P6): mọi dòng mới/sửa của nhánh đều được chạy. Dòng thiếu chỉ là mã có sẵn trên `main`: `migrate_check.py:224-228` (`_start_postgres`, chỉ chạy khi thiếu `DATABASE_URL`), `:254`, `new_revision.py:95`, `lint_migrations.py:332` (ba dòng `if __name__ == "__main__"`).

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (321 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (279 file) |
| 4 | `lint-imports` | đạt (9 kept, 0 broken) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf` bị chạm; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5) |
| 6 | `lint_migrations` → `migrate_check` | đạt (4 revision; 10/10 bước con, gồm "model khớp DB" và "tên CHECK khớp model") |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt: Smoke, H1 186 mẫu. H3/H4/H5 `không áp dụng` là **hợp lệ** vì B1-02, B3-05, B4-01 chưa hợp nhất |
| 8 | openapi | đạt (nhánh worker: xuất được, 8174 byte) |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (đầu phiên và cuối phiên, sau khi xoá `.cache/rv-dbtools/`) |
| `changes/<mã>.md` của B0-01, B0-03 | đạt: cả hai đã có trên `main`. Nhánh chỉ mang FIX, không bàn giao prompt mới |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt: cả 8 commit, dài nhất 68 ký tự (`76ec3fd`) |
| Trailer đọc được (R-36b) | đạt. `%(trailers:key=Prompt)` in `B0-03` cho 7 commit và `B0-01` cho `76ec3fd`. `Fix:` in đúng `FIX-039` / `FIX-041` / `FIX-040` / `FIX-042` / `FIX-041`. Hai commit merge và `6769d63` không có `Fix:`, đúng vì không phải commit sửa |
| Đụng `docs/charter/*`, `docs/contracts.toml`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/verify/*` | không. Diff chỉ có 7 file: `DEBT.md`, `packages/db/{migrate_check,new_revision}.py` và hai test, `tools/lint_migrations.py`, `tools/tests/test_lint_migrations_main.py` |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không. Dòng `noqa` duy nhất trong diff là `# noqa: BLE001 — …` có sẵn, chỉ dời từ closure `step` sang `_run_step` |

File ngoài cột "Sở hữu" của B0-03 là `tools/lint_migrations.py` và `tools/tests/test_lint_migrations_main.py` (B0-01, FIX-042). Đoạn "Giao việc FIX-039..FIX-051 (đợt 2)" của `docs/fixes.md` giao cả bốn FIX cho nhánh này và FIX-042 [4] cho phép đúng hai file đó. Commit `76ec3fd` mang `Prompt: B0-01`. Không có điều kiện dừng sớm nào kích hoạt.

## Công cụ kiểm tại chỗ

Probe chạy bằng `bash tools/verify/run.sh shell < probe.sh` (04:42:30Z, lúc đó 1 container `verify-run` khác; probe độ phủ 04:46:01Z, cũng 1), trên bản sao `/tmp/w` trong container, `PYTHONPATH=/tmp/w`, `pytest -p no:cacheprovider -o addopts=`. Bản file của `main` (`f5cc758`), của `eda31d6` và của `135dc42` đặt tạm dưới `.cache/rv-dbtools/` (git-ignore) rồi `cp` đè bên trong container. `.cache/rv-dbtools/` đã xoá sau khi chạy. Output ở `…/scratchpad/probe.out`, `…/scratchpad/probe2.out`.

- **P1: FIX-039, đỏ trước / xanh sau, và CLI không đổi.**
  - `new_revision.py` của `main` + test của nhánh: **3 failed, 11 passed** (`TypeError: main() got an unexpected keyword argument 'clock'`). Đúng số tác giả ghi.
  - Tái hiện triệu chứng gốc NO-065: mã **và** test của `main`, plugin lùi `TODAY` một ngày ở `pytest_collection_finish`: **2 failed, 11 passed**. Đúng `F.F` của lượt đỏ gốc.
  - Mã và test của nhánh, plugin cho `SystemClock.now` **nhảy một ngày mỗi lần đọc** (4 lần đọc từ các test còn dùng đồng hồ thật): **14 passed**. Không plugin: **14 passed**. Nghĩa là không còn test nào của file phụ thuộc ngày thật: các test còn dùng `SystemClock` đều không glob theo ngày (`_existing` so theo mã prompt, bỏ qua ngày).
  - CLI dưới `TZ=Etc/GMT+12` (lúc chạy: UTC `20260922T0443`, giờ địa phương `20260921T1643`): `python -m packages.db.new_revision --code B9-99 --slug probe_utc` của **cả `main` lẫn nhánh** đều tạo `r20260922_b9_99_probe_utc.py`, thoát 0. CLI vẫn đi qua `SystemClock` (`sys.exit(main())`, `clock=None` → `SystemClock()`), vẫn lấy **ngày UTC** như trước, không lấy ngày địa phương.
- **P2: FIX-040, hành vi không đổi.**
  - `test_migrate_check.py` của `main` (12 test) chạy trên `migrate_check.py` của nhánh: **12 passed**.
  - `python -m packages.db.migrate_check` trên repo (Testcontainers tự dựng Postgres), bản `main` và bản nhánh: cùng thoát **0**, `diff` của hai output **giống hệt** (10 dòng bước theo cùng thứ tự, cùng tên, cùng kết luận).
  - Đối chiếu mã: `alembic(argument)` rẽ nhánh theo chuỗi (`"base"`/`"-1"` → `downgrade`, còn lại → `upgrade`) thay bằng `_alembic(command.upgrade|downgrade, config, revision)` với đúng cặp đối số cũ ở cả 5 chỗ gọi. `_run_step` bắt `Exception` như closure `step` cũ. Việc ghi `results` và `break` ở bước hỏng đầu vẫn nằm trong `try/finally` quanh `engine.dispose()`. Lambda trong `_steps` bắt tham số của hàm, không bắt biến vòng lặp, nên không có lỗi late binding.
- **P3: FIX-041, đỏ trước / xanh sau, và lập luận của `3b4f01c`.**
  - `migrate_check.py` của `main` + test của nhánh, `-k "native_type or ddl_if"`: **4 failed, 1 passed** (bốn test `native_type`; test `ddl_if` xanh vì `main` chưa lọc gì).
  - `migrate_check.py` của `135dc42` (FIX-041 lượt đầu, trước `3b4f01c`) + test của nhánh: **1 failed, 4 passed**, test đỏ là `test_column_check_with_ddl_if_is_still_expected`.
  - Nhánh: `packages/db/tests` **98 passed**.
  - Mã SQLAlchemy 2.0.54 trong venv của cổng (khớp `uv.lock`): `compiler.py:6893-6906` `visit_create_column` phát `self.process(constraint) for constraint in column.constraints` **không qua cổng nào**. `create_table_constraints` (`:6908`) chỉ lọc `table._sorted_constraints` bằng `constraint._should_create_for_compiler(self)` (`:6936`). `schema.py:4162-4172` cho thấy hàm đó xét `_create_rule` rồi `ddl_if`. Lập luận của `3b4f01c` **đúng**: chỉ `CHECK` mức bảng đi qua cổng, nên chỉ được lọc `CHECK` mức bảng.
  - **Probe tương đương độc lập** (chính "đường nâng cấp" mà comment R-05 nêu): metadata thử có 14 loại `CHECK`. Gồm: mức cột thường; mức cột có `ddl_if(dialect="sqlite")` và `ddl_if(dialect="postgresql")`; `Boolean(create_constraint=True)` không tên và có tên; `Boolean(...).with_variant(Integer(), "postgresql")`; `Enum` native và `Enum(native_enum=False)` có `create_constraint=True`; mức bảng thường; mức bảng có `ddl_if` Postgres, `ddl_if` SQLite, `ddl_if(callable_=…)` đúng và sai. Chạy `metadata.create_all` trên `postgres:16-alpine` → tập tên `CHECK` trong `pg_constraint` **bằng đúng** tập `CONSTRAINT … CHECK` của `CreateTable(...).compile(dialect)` (8 tên). Kết quả `_check_name_drift`:
    - `main`: ném `InvalidRequestError` (Boolean không tên);
    - `eda31d6` và `135dc42`: `CHECK thừa trong DB: ['ck_t1_n_sqlite']`;
    - **nhánh: `''`**. Tức là với mọi loại trên, tập tên model của nhánh trùng đúng tập tên DDL phát ra: **không bỏ sót `CHECK` mức bảng nào** (kể cả `CHECK` gắn `Enum` không native, vẫn được đòi), và không đòi thừa.
    - Đổi tên `ck_t1_m_pos` (mức bảng) và `ck_t1_kind_p` (gắn `Enum` không native) trong DB → nhánh báo đúng hai cặp thừa/thiếu. Bộ lọc không làm mù bước.
  - Comment R-05 (`migrate_check.py:100-104`) nói "bản sau đổi tên thì bước ném `AttributeError`". Điều này đúng với repo hiện tại: `Base.metadata` có `CHECK` mức bảng (`packages/db/models/auth.py:68-96`, `idempotency.py:66-67`), nên thuộc tính được đọc ở mọi lượt cổng.
- **P4: FIX-042, đỏ trước / xanh sau, và hành vi không đổi.**
  - `lint_migrations.py` của `main` + test của nhánh: **2 failed, 32 passed** (`test_tên_thêm_vào_destructive_chỉ_được_miễn_cho_contract[True|False]`).
  - Test của `main` trên lint của nhánh: **32 passed**. Nhánh: **34 passed**.
  - **So vi phạm độc lập** (không dùng bộ 168 ca của tác giả): 3 316 thân revision sinh ra (seed cố định). Gồm 59 đoạn mã phủ mọi luật và biên: `nullable=0`/biến/`**kw`, `add_column` nhiều `Column`, `Column` trần, SQL bytes, chuỗi ghép, f-string, `op.execute()` rỗng, `create_index` thiếu bảng / bảng bằng biến / `table_name=` kwarg / bảng tạo cùng revision, `with` lồng hai context có `if` bên trong, `batch_alter_table` làm context. Kết hợp với 8 dạng khai `revision` (thường, `AnnAssign`, thiếu, không hằng, `_fix1`, merge, sai mẫu, quá 32 ký tự), 4 chế độ (thường / contract đã đăng ký / contract chưa đăng ký / `# contract:` sau dòng 10), gọi ở mức module, và `downgrade()` có thao tác phá huỷ. Lint của `main` và của nhánh cho ra **11 850 vi phạm, 0 ca khác nhau** (so cả file, luật, chi tiết, thứ tự). Trên `packages/db/migrations/versions` thật: cả hai `[]`.
- **P5: R-08, đo lại** (`ruff check --isolated --select C901 --config "lint.mccabe.max-complexity = 0"` cho CC; dòng và độ lồng khối điều khiển đếm bằng AST):

  | hàm | `main` | nhánh |
  |---|---|---|
  | `lint_migrations._lint_body` | 78 dòng, CC 28, lồng 5 | 18 dòng, CC 5, lồng 3 |
  | `migrate_check.run_checks` | 82 dòng, CC 13, lồng 3 | 25 dòng, CC 3, lồng 3 |
  | `lint_migrations._in_autocommit_block` | CC 5, lồng 4 | CC 1, lồng 0 |
  | `lint_migrations._collect_created_tables` | CC 4, lồng 3 | CC 1 |
  | `new_revision.main` | 33 dòng, CC 7 | 38 dòng, CC 7, lồng 1 |
  | `migrate_check._check_name_drift` | 20 dòng, CC 1 | 36 dòng, CC 1, lồng 0 |
  | hàm mới (`_check_*`, `_const_str`, `_is_const`, `_keywords`, `_ancestors`, `_one_head`, `_alembic`, `_seed_twice`, `_only_version_table`, `_metadata_matches`, `_check_names_match`, `_steps`, `_run_step`) | — | ≤ 14 dòng, CC ≤ 5 |

  Trong ba file, CC lớn nhất nay là 7 (`new_revision.main`, `_validate_revision_id`), hàm dài nhất 38 dòng: mọi hàm ≤ 50 dòng, lồng ≤ 3, CC ≤ 10. Số đo trong báo cáo và dòng `DEBT.md` khớp. Riêng `new_revision.main` tác giả ghi "CC ≤ 9, đếm tay"; đo thật là 7.
- **P6: độ phủ ba file sản phẩm** (`coverage run` riêng `packages/db/tests` + hai file test lint, `branch = true`): `migrate_check.py` thiếu 224-228, 254; `new_revision.py` thiếu 95; `lint_migrations.py` thiếu 332. Đều là dòng có sẵn trên `main`, không dòng nào của nhánh.
- **P7: NO-080.** `docker inspect` một container `verify-run` đang chạy: `HostConfig.AutoRemove=true`. Mount chỉ có `/appfront`, `/src-out/contract-samples`, `/var/run/docker.sock`, `/work`, `/src`, tức là **không có** mount host nào cho `/src-out` hay `/src-out/verify` (xem Nit #1). Cách tạm mà dòng nợ nêu (`docker logs -f` ngay khi container lên) **dùng được**: lượt cổng của phiên này giữ đủ bảng bước 5 và `coverage_gate` bằng đúng cách đó (`verify.dockerlogs`, 268 dòng).

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | R-34 · OBS-01 | Dòng NO-080 đúng sự thật ở phần triệu chứng (AutoRemove, `docker logs` → `no such object` sau khi thoát, chỉ còn mã thoát qua `docker wait`). Nhưng cột nguyên nhân viết "không được ghi ra thư mục mount của host (`/src-out`)" và hướng sửa viết "`/src-out/verify/<lượt>.log` (mount host)". Hai câu này ngụ ý `/src-out` đã là mount host, trong khi `verify.yml` chỉ mount `/src-out/contract-samples` (probe P7). `run.sh` gắn `-v "$CACHE_DIR/src-out/<việc>:/src-out/<việc>"` cho `lock`/`openapi`/`merge-heads`, riêng `verify` thì không. Không gây hại vì FIX-053 [5] trên `main` đã ghi đúng (`/src-out/…` → `.cache/src-out/…` của worktree) | `DEBT.md:96` | Khi giải xung đột, sửa cụm "(mount host)" thành "(mount mới do `run.sh` gắn như `lock`/`openapi`: `.cache/src-out/verify`)", và đổi ô `⬜` → `🔧 FIX-053 · nhánh fix/b0-01-gate-log-debts` cho khớp `docs/fixes.md:62` của `main` |
| 2 | Nit | TEST-01 · R-14 | Cổng mức bảng dùng `_should_create_for_compiler`, xét cả `_create_rule` lẫn `ddl_if`, và comment R-05 nói cả hai. Test của nhánh chỉ chốt nửa `_create_rule` (`Boolean`/`Enum` native) và vế "mức cột **không** lọc". Chưa test nào chốt vế `ddl_if` **mức bảng** (`CheckConstraint(...).ddl_if(dialect="sqlite")` trong `Table(...)` không bị đòi trong DB). Hành vi đúng (probe P3: `ck_t1_m_sqlite`, `ck_t1_m_callable_no` không bị đòi) nhưng không được chốt | `packages/db/tests/test_migrate_check.py:213` | Tuỳ tác giả, không chặn merge: thêm tham số `table_ddl_if` vào `test_check_bound_to_native_type_passes`, hoặc một test `test_table_check_with_foreign_ddl_if_is_not_expected` |
| 3 | Nit | R-01 | Ba file bị chạm còn 17 hàm không docstring, đều có sẵn trên `main`, ngoài phạm vi [5] của bốn FIX: `_lint_file` (dòng gọi `_lint_body` có sửa), `_validate_revision_id`, `_call_attr`, `_find_downgrade`, `_load_contracts`, `run`, `Report.add/ok`; `migrate_check._say/_table_counts/_compare/_start_postgres/main`; `new_revision._say/revision_id/_existing/build_parser`. Nhánh **giảm** số này từ 20 xuống 17, và mọi hàm mới đều có docstring | `tools/lint_migrations.py:266`; `packages/db/migrate_check.py:54,69,83,222,231`; `packages/db/new_revision.py:29,33,37,45` | Không chặn. Nếu người điều phối muốn theo dõi, mở một dòng nợ (xem "Sổ nợ") cho B0-01 và B0-03, gom vào lần FIX kế tiếp chạm các file này |

**P0: 0 · P1: 0 · P2: 0 · P3: 0 · Nit: 3**

## Những chỗ đã soi kỹ và **đạt**

- **FIX-039 (R-18, R-19).** `main(argv, *, clock: Clock | None = None)`. Ngày đọc `(clock or SystemClock()).now()` **đúng lúc gọi**, không lúc nhập. Sửa ở gốc: `new_revision` nhận đồng hồ, không chỉ vá test. `TODAY` lúc nhập bị bỏ hẳn. Hai test đỏ gốc ghim bằng `fake_clock`. Test mới đặt 23:59:59Z, dựng kỳ vọng rồi `advance(2 s)` trước khi gọi, khẳng định cả vế dương (`r20260102_…`) lẫn vế âm (không có file ngày cũ), đúng spec [6]. Người gọi `new_revision.main` chỉ có CLI và test (`grep`). Tham số chỉ khoá (`*`) nên không vỡ lời gọi vị trí nào.
- **FIX-040 (R-08, R-10).** Mười bước lên mức module, nhận `config`/`engine`/`target`/`seed_runner` qua tham số. `run_checks` còn vòng lặp và dọn engine. Tên bước, thứ tự, mã thoát không đổi (P2, output giống hệt). Không thêm tầng trừu tượng: `Step` là bí danh kiểu, `_steps` là danh sách, không lớp, không registry.
- **FIX-041 (R-05, R-19).** Lọc đúng chỗ mọi đường đi qua (`_check_name_drift` là điểm duy nhất tập `CHECK` model được dựng). Comment R-05 nêu API riêng, ngưỡng (2.0.54, khớp `uv.lock` và venv của cổng), hệ quả khi SQLAlchemy đổi tên (đỏ, không xanh giả) và đường nâng cấp. Probe P3 đã chạy chính đường nâng cấp đó và ra cùng kết quả. Chọn `_should_create_for_compiler` thay vì `_create_rule` đơn lẻ là **đúng hơn** chữ của spec [5]: đó là đúng cổng mà DDL dùng. Test mới khẳng định cả vế "mức cột vẫn bị đòi" **và** chính giả định của nó (`CreateTable(...).compile` phát `ck_thing_n_positive`), nên SQLAlchemy đổi hành vi `visit_create_column` thì test đỏ ngay.
- **FIX-042 (R-07, R-08).** Mỗi luật một hàm. Cờ `destructive` trên từng vi phạm thay cho `Report()` dùng để bỏ đi. `_DESTRUCTIVE_CALL_NAMES` tách khỏi `_BATCH_ALTER_TABLE`. Năm chỗ chép tay phép thử "hằng chuỗi"/"hằng bool" gom về `_const_str`/`_is_const`/`_keywords`. Phạm vi miễn trừ của FIX-038 **không đổi**: `batch_alter_table`, SQL không hằng và `create_index` thiếu `CONCURRENTLY`/ngoài `autocommit_block` vẫn mang `destructive=False`, nên vẫn báo trong contract đã đăng ký (P4: 0 khác trên 3 316 ca, gồm đủ ba chế độ contract). Test chốt mới đúng spec [6]. Bỏ tham số `source` và `node` không dùng: người gọi duy nhất là `_lint_file` (`grep`).
- **Hợp nhất trong nhánh.** Hai lần gộp `main` (`135dc42`, `e5d0247`) giải xung đột `DEBT.md` đúng: NO-067 lấy của `main`, NO-065 và NO-068..070 lấy của nhánh. Không mất dòng nào của `main` @ `f5cc758`.
- **Kích thước.** 7 file, +331/−180, phần lớn là tái cấu trúc. Dưới trần 400 dòng logic của MNT-05.

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | FIX-041 hai commit (`eda31d6`, rồi `3b4f01c` sau một lần merge) vì `visit_create_column` phát mọi `CHECK` trong `Column(...)` | **Đứng được.** Mã SQLAlchemy 2.0.54 xác nhận (P3). Bản `135dc42` đỏ `1 failed` và báo thừa `ck_t1_n_sqlite` trên probe độc lập. Sửa bằng commit bổ sung cùng `Fix: FIX-041` thay vì rebase là đúng luật không viết lại lịch sử đã chia sẻ |
| 2 | Dùng `_should_create_for_compiler` thay cho `_create_rule`; trình biên dịch dựng với `CreateSchema("public")` vì `DDL(...)` chưa gõ kiểu | **Đứng được.** Đúng cổng của DDL (bọc cả `_create_rule` và `ddl_if`). `mypy --strict` đạt |
| 3 | FIX-042 chạm thêm `_module_level_str`, `_collect_created_tables`, `_in_autocommit_block` | **Đứng được.** Cùng file [4], cùng việc (R-07: năm bản chép của một phép thử). `_in_autocommit_block` lồng 4 → 0 (trước đó trái R-08). Hành vi không đổi (P4) |
| 4 | FIX-040 truyền thẳng `command.upgrade`/`command.downgrade` vào `_alembic` | **Đứng được.** Cùng lời gọi, cùng đối số (P2) |
| 5 | Một lượt `run.sh shell` khởi chạy lúc đã có 3 container `verify-run` | Ghi nhận, không phải finding của mã: sai quy trình đã tự khai, sau đó có vòng chờ. Đếm rồi khởi chạy vẫn có thể đua với worker khác (phiên này cũng chịu cùng giới hạn đó) |
| 6 | Log bước 4–8 và độ phủ của lượt tác giả mất; người điều phối chọn để `/merge-review` đo lại | **Đã đo lại** ở phiên này: thoát 0, `2024 passed, 0 failed, 10 skipped`, độ phủ ở đầu file. `6769d63` sau lượt của tác giả chỉ đụng `DEBT.md`; lượt của tôi chạy trên chính `6769d63` |
| 7 | `main` đã gộp vào nhánh hai lần; không gộp thêm | Đúng. `main` nay @ `885a9f1`, `merge-tree` chỉ xung đột `DEBT.md` |

## Hợp nhất với `main` (`885a9f1`)

- `git merge-tree --write-tree main HEAD` chỉ báo `CONFLICT (content): Merge conflict in DEBT.md`, một khối ở dòng 95–103:
  - phía `main`: NO-075 (`🔧` FIX-052), NO-076, NO-077, NO-079;
  - phía nhánh: NO-075 (`⬜`, bản cũ), NO-080.
  - **Cách giải:** giữ nguyên khối của `main`, nối dòng NO-080 của nhánh sau NO-079. Nên đổi NO-080 sang `🔧 FIX-053 · nhánh fix/b0-01-gate-log-debts`, vì `docs/fixes.md:62` của `main` đã mở FIX-053 cho nó (Nit #1).
  - NO-065, NO-068..070 (`✅`) gộp sạch.
- Người gọi các API nhánh đổi: `new_revision.main` chỉ có CLI và `packages/db/tests/test_new_revision.py`. `run_checks` và `_check_name_drift` chỉ có `migrate_check.main` và `packages/db/tests/test_migrate_check.py` (`tools/contract/check.py:290` là một `run_checks` khác, không liên quan). `_lint_body`, `_BANNED_CALL_NAMES`, `_in_autocommit_block` không có người gọi nào ngoài `tools/lint_migrations.py`. Trên `main` không có mã mới (B0-06, B0-07, B1-01, B3-01, FIX-043..051) nhập các tên này. `grep` toàn repo trên nhánh đã gộp `f5cc758`, và `git diff f5cc758 885a9f1` không đụng `packages/db`, `tools/`.
- Các commit mới trên `main` (FIX-043..047 và tài liệu) không chạm `packages/db` hay migration, nên bước 6 sau khi gộp vẫn là 4 revision, 1 head.

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Nợ nhánh đóng có dòng `✅`, ngày đóng, nói đúng sự thật | đạt: NO-065 (P1 khớp `3 failed, 11 passed` → `14 passed`), NO-068 (số đo khớp P5, `2 failed` → `34 passed` khớp P4), NO-069 (số đo khớp P5, `96`/`96` và hành vi khớp P2), NO-070 (`4 failed` → xanh, bổ sung `1 failed` → `98 passed` khớp P3). Mỗi dòng đổi `✅` trong chính commit sửa |
| Mọi nợ tác giả nêu đều có dòng | đạt: NO-080 (mới, `⬜`, P3) |
| NO-080 đúng sự thật, đúng chủ, đúng mức | **Sự thật:** đúng (P7: `AutoRemove=true`, output chỉ qua stdout của client; cách tạm `docker logs -f` dùng được). Cụm "mount host" chưa chính xác (Nit #1). **Chủ:** đúng, B0-01 (`tools/verify/*` chỉ B0-01 sửa theo CLAUDE.md; `verify.yml` ghi "B0-01 [6]B"). **Mức:** P3 đúng. Cùng họ với NO-075 (P3, mất bảng cổng). Mã thoát thật vẫn lấy được, không ảnh hưởng mã sản phẩm, có cách tạm |
| Nợ P0/P1 còn `⬜`/`🔧` | không có trên nhánh hay trên `main` |
| Nợ do review này chỉ ra | ba Nit, không bắt buộc ghi. Dòng tuỳ chọn cho Nit #3 nếu người điều phối muốn theo dõi (id do người điều phối cấp): |

- `| ⬜ | NO-<nnn> | 2026-09-22 | | 17 hàm không docstring trong tools/lint_migrations.py (_validate_revision_id, _call_attr, _find_downgrade, _lint_file, _load_contracts, run, Report.add/ok), packages/db/migrate_check.py (_say, _table_counts, _compare, _start_postgres, main), packages/db/new_revision.py (_say, revision_id, _existing, build_parser) | Viết trước R-01 (RULE-CODE bản đầu); các FIX sau chỉ thêm docstring cho hàm chúng viết | B0-01 (tools/lint_migrations.py) · B0-03 (packages/db/*.py) | Nit | mở — review merge 2026-09-22 fix/b0-03-migration-tool-debts finding #3; gom vào FIX kế tiếp chạm các file này |`

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit #2) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 (Nit #1) | 0,25 |
| MNT – Bảo trì | 3 % | 5 (Nit #3) | 0,15 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,15 = **5,00 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt tôi tự chạy, có log giữ hai bản. Đây là nguồn duy nhất cho số của nhánh: `2024 passed, 0 failed, 10 skipped`; độ phủ tổng 99,35 % / 97,52 %, `packages/db` 98,81 % / 97,22 %, `tools` 98,68 % / 95,64 %. Không có P0–P3, điểm 5,00.

- **FIX-039** sửa gốc: ngày đọc từ `Clock` tiêm được, đúng lúc gọi. Triệu chứng gốc NO-065 tái hiện đúng `2 failed` trên `main` và biến mất trên nhánh, kể cả khi đồng hồ hệ thống nhảy ngày giữa các lần đọc. CLI vẫn dùng `SystemClock` và ngày UTC (probe dưới `TZ=Etc/GMT+12`).
- **FIX-040** là tái cấu trúc thuần: test cũ xanh, output `migrate_check` trên repo giống hệt từng dòng.
- **FIX-041** đúng về cơ chế. Mã SQLAlchemy 2.0.54 xác nhận chỉ `CHECK` mức bảng đi qua cổng. Trên 14 loại `CHECK`, tập tên model của nhánh trùng đúng tập tên mà `create_all` tạo ra, và lệch tên mức bảng vẫn bị bắt.
- **FIX-042** giữ nguyên vi phạm (cả thứ tự) trên 3 316 ca sinh độc lập, và giữ nguyên phạm vi miễn của FIX-038.
- Mọi hàm bị chạm đạt R-08.
- NO-080 đúng sự thật, đúng chủ, đúng mức (một cụm chữ chưa chính xác, Nit #1).

Điều kiện cho phiên merge:

1. Gộp bằng `git merge --no-ff` (R-36: nhánh mang trailer của **B0-03** và **B0-01** + `Fix: FIX-039/040/041/042`), **không** squash.
2. Giải xung đột `DEBT.md` như mục "Hợp nhất với `main`": giữ khối NO-075..NO-079 của `main`, nối NO-080 của nhánh. Nên đổi NO-080 sang `🔧 FIX-053 · nhánh fix/b0-01-gate-log-debts` và sửa cụm "(mount host)" (Nit #1).
3. Người điều phối điền sha vào cột "Commit" của `docs/fixes.md:48-51`: FIX-039 `5ce33f0`, FIX-040 `646740e`, FIX-041 `eda31d6` + `3b4f01c`, FIX-042 `76ec3fd` (`--no-ff` giữ nguyên các sha này).
4. Nit #2, #3 do tác giả/người điều phối tự quyết, không chặn merge. Dòng nợ tuỳ chọn cho #3 viết sẵn ở "Sổ nợ".
