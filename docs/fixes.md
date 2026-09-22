# FIXES — Sổ mã FIX

> `docs/charter/FIX.md` luật 5: mỗi FIX có mã `FIX-<nnn>` tăng dần, **không dùng lại**,
> ghi ở đây. Người điều phối giữ file này; worker chỉ đọc để biết mã kế tiếp.
> Thông điệp commit của FIX mang **hai** trailer: `Prompt: <mã prompt sở hữu file>` và
> `Fix: FIX-<nnn>` (BE-00 §13.2).

| Mã | Ngày | Cho prompt | Nợ | Một câu | Commit |
|---|---|---|---|---|---|
| FIX-001 | 2026-09-20 | B0-01 | NO-001 | `run.sh lock` hỏng `FileExistsError` vì thư mục ra là mount point | `c5bf22e` |
| FIX-002 | 2026-09-20 | B0-03 | NO-002 | Không có trần bắt tay tường minh nên cổng kết tội nhầm migration | `68cdebe` |
| FIX-003 | 2026-09-20 | B0-01 | NO-031 | Ba test của `case_gate` chốt "repo chưa có thao tác/task nào" làm bất biến | `cdee48c` |
| FIX-004 | 2026-09-20 | B0-03 | NO-032 | `test_new_revision` ghim head `r20260920_b0_03` làm hằng | `960dced` |
| FIX-005 | 2026-09-20 | B0-05 | NO-033 | Hai test của `messaging` chốt "sổ task và beat rỗng" | `c952c40`, `d032787` |
| FIX-006 | 2026-09-21 | B0-01 | NO-008 | `_clean_dir` nuốt lỗi xoá file trong thư mục ra | `a61b92c` |
| FIX-007 | 2026-09-21 | B0-01 | NO-042 | `test_services` bắt tay Postgres dùng chung với trần 5 s | `f3559f1` |
| FIX-008 | 2026-09-21 | B0-01 | NO-043 | Mẫu golden không được chép ra `contract-samples/` cuối lượt | `d1c72d5` |
| FIX-009 | 2026-09-21 | B0-01 | NO-007 | Chặng `host.docker.internal` tới testcontainers kẹt ~68 s | `3ca1463`, `caaf5ab` |
| FIX-010 | 2026-09-21 | B0-03 | NO-036 | `db_sessionmaker` dùng trần bắt tay 10 s của đường request | `e3f2598` |
| FIX-011 | 2026-09-21 | B0-04 | NO-009 | S3 5xx có thân XML lọt ra thành 500 thay vì 503 | `f070775` |
| FIX-012 | 2026-09-21 | B0-04 | NO-010 | `_delete_under` xoá từng object (N+1) | `6c256d4` |
| FIX-013 | 2026-09-21 | B0-04 | NO-011 | `signed_url(inline)` tốn `HEAD` cho khoá do server đặt tên | `f72590b` |
| FIX-014 | 2026-09-21 | B0-04 | NO-012 | `LocalDiskStorage.delete_prefix` nuốt lỗi xoá | `280dbd4` |
| FIX-015 | 2026-09-21 | B0-04 | NO-013 | `list_prefix` nạp cả danh sách vào RAM | `b298535` |
| FIX-016 | 2026-09-21 | B0-04 | NO-014 | `S3Storage.put` để lỗi đĩa của bộ đệm ra 500 | `1690533` |
| FIX-017 | 2026-09-21 | B0-04 | NO-015 | `ensure_bucket` nuốt mọi `S3Error` của CORS | `52ccb1b` |
| FIX-018 | 2026-09-21 | B0-04 | NO-016 | Hai test storage phụ thuộc đồng hồ thật | `e8890c5` |
| FIX-019 | 2026-09-21 | B0-04 | NO-017 | Phần B0-04 của NO-017: khẳng định test và chú thích `_message` | `5e0a831` |
| FIX-020 | 2026-09-21 | B0-05 | NO-022 | Chưa test đường giao lại thật khi worker chết | `b6c54ea` |
| FIX-021 | 2026-09-21 | B0-05 | NO-023 | Bộ đếm giao lại tốn hai lượt Redis, `EXPIRE` hỏng thì sống mãi | `382000c` |
| FIX-022 | 2026-09-21 | B0-05 | NO-024 | `asyncio.Runner` của worker không bao giờ đóng | `929fa9b` |
| FIX-023 | 2026-09-21 | B0-05 | NO-025 | `SafeLock.hold` không chặn được thân nuốt huỷ hay chạy đồng bộ dài | `befdf78` |
| FIX-024 | 2026-09-21 | B0-05 | NO-027 | Test khoá chốt hành vi bằng đồng hồ thật, biên 300 ms | `f3e3058` |
| FIX-025 | 2026-09-21 | B0-05 | NO-028 | `release` trong `finally` che ngoại lệ thật của thân | `970d779` |
| FIX-026 | 2026-09-21 | B0-05 | NO-029 | Bộ đếm rào `lock:{name}:fence` không có ngưỡng ghi rõ | `11084c1` |
| FIX-027 | 2026-09-21 | B0-05 | NO-030 | `_fail` ghi `repr` đầy đủ của ngoại lệ module khác | `aa60797` |
| FIX-028 | 2026-09-21 | B0-06 | NO-044 | Hai bộ khớp (method, đường) → thao tác trùng nhau | `d3b25b0` |
| FIX-029 | 2026-09-21 | B0-06 | NO-053 | Năm test lõi của B0-06 chốt "chưa có B1-01" (verifier DenyAll, đúng hai router, đúng ba thao tác) | `1e2d146` |
| FIX-030 | 2026-09-21 | B0-06 | NO-054 | `rate_limit` chỉ nhận hạn mức số nguyên, module có cấu hình đọc lười phải dựng limiter mỗi request | `971a1a1` |
| FIX-031 | 2026-09-21 | B0-06 | NO-055 | `api_env` không `FLUSHDB` DB an toàn giữa các test | `9f80576` |
| FIX-032 | 2026-09-22 | B0-01 | NO-048 | Lượt verify lạnh chạy `npm ci` (tải mạng) ngay trong bước 5 | `02f2b64` |
| FIX-033 | 2026-09-22 | B0-01 | NO-049 | `case_gate` chưa xuất hàm tách tên test công khai | `a21a0ac` |
| FIX-034 | 2026-09-22 | B0-07 | NO-049 | Bộ ghi golden nhập hằng riêng `_TEST_*_RE` của `case_gate` | `84fed27` |
| FIX-035 | 2026-09-22 | B0-07 | NO-052 | `tools.contract.check` không `--build-dir` để lại `/tmp/contract-*` | `1ca38e2` |
| FIX-036 | 2026-09-22 | B0-03 | NO-057 | `migrate_check` không so tên `CHECK` của DB với model | `593bcea` |
| FIX-037 | 2026-09-22 | B0-06 | NO-057 | Hai `CHECK` của `idempotency_records` lặp tiền tố tên | `4e8e2a5` |
| FIX-038 | 2026-09-22 | B0-01 | NO-058 | `lint_migrations` không miễn revision contract đã đăng ký: đường contract của BE-00 §6.1 không dùng được | `f37c52e` |
| FIX-039 | 2026-09-22 | B0-03 | NO-065 | `test_new_revision` đóng băng ngày lúc nhập, đỏ khi bộ test vắt qua nửa đêm UTC | `5ce33f0` |
| FIX-040 | 2026-09-22 | B0-03 | NO-069 | `migrate_check.run_checks` vượt R-08 (82 dòng, CC 13) | `646740e` |
| FIX-041 | 2026-09-22 | B0-03 | NO-070 | Bước "tên CHECK khớp model" đỏ giả với CHECK gắn kiểu | `eda31d6`, `3b4f01c` |
| FIX-042 | 2026-09-22 | B0-01 | NO-068 | `lint_migrations._lint_body` vượt R-08 (78 dòng, CC 28) | `76ec3fd` |
| FIX-043 | 2026-09-22 | B0-02 | NO-060 | Luật khoá object chưa có ở `packages/core` | `f6fb907` |
| FIX-044 | 2026-09-22 | B0-04 | NO-060 | `storage.keys` giữ bản riêng của luật khoá object | `59e9e32` |
| FIX-045 | 2026-09-22 | B5-01 | NO-060 | `ml_contracts.payloads` chép luật khoá object của `storage` | `4aad113` |
| FIX-046 | 2026-09-22 | B0-04 | NO-073 | `_SERVER_NAMED_RE` chép tay luật id tầng của `core/ids.py` | `09e4b21` |
| FIX-047 | 2026-09-22 | B0-04 | NO-072 | Test FIX-012 không chạm biên 1000 khoá/lượt `DeleteObjects` | `1bd891b` |
| FIX-048 | 2026-09-22 | B1-01 | NO-066 | `test_auth_refresh__C11_parallel` chập chờn (21×401 thay vì 20) | nhánh `fix/b1-01-parallel-refresh-flake` |
| FIX-049 | 2026-09-22 | B0-01 | NO-067 | Bộ lọc case của `_found_cases_by_op` chưa test nào chạm | `3cb7abf` |
| FIX-050 | 2026-09-22 | B0-05 | NO-074 | `SafeLock` chưa công khai đường trả khoá lặng lẽ | `7e56b05` |
| FIX-051 | 2026-09-22 | B5-01 | NO-074 | `gpu.py` chép logic trả khoá lặng lẽ của `SafeLock` | `f6ee1dc` |
| FIX-052 | 2026-09-22 | B0-01 | NO-075 | Chép mẫu golden hỏng thì mất bảng cổng, lượt đạt vẫn thoát 1 | nhánh `fix/b0-01-gate-log-debts` |
| FIX-053 | 2026-09-22 | B0-01 | NO-080 | Log cổng mất khi shell bọc `run.sh verify` bị cắt | nhánh `fix/b0-01-gate-log-debts` |
| FIX-054 | 2026-09-22 | B0-02 | NO-076 | `core/ids.py` chưa phơi hàm kiểm thân ULID không tiền tố | nhánh `fix/b0-04-key-layout-debts` |
| FIX-055 | 2026-09-22 | B0-04 | NO-076 | `storage.keys._ULID_RE` chép thân ULID của `core/ids.py` | nhánh `fix/b0-04-key-layout-debts` |
| FIX-056 | 2026-09-22 | B0-02 | NO-077 | Bố cục tiền tố lượt tải lên chưa có ở `packages/core` | nhánh `fix/b0-04-key-layout-debts` |
| FIX-057 | 2026-09-22 | B0-04 | NO-077 | `storage.keys.upload_prefix` giữ bản riêng của bố cục dùng chung | nhánh `fix/b0-04-key-layout-debts` |
| FIX-058 | 2026-09-22 | B5-01 | NO-077 | `ml_contracts._upload_prefix` dựng lại bố cục khoá của `storage` | nhánh `fix/b0-04-key-layout-debts` |
| FIX-059 | 2026-09-22 | B0-05 | NO-078 | Worker Celery thử để logger gốc ở ERROR sau test messaging | nhánh `fix/b0-01-gate-log-debts` |

> **Giao việc FIX-003..005.** Ba FIX này sửa test của prompt khác ngay trên nhánh B0-06 (ngoại lệ của K27):
> người điều phối chọn "Tôi FIX ngay trong phiên này" ngày 2026-09-20 khi cổng bước 5 đỏ vì chúng,
> và xác nhận lại ngày 2026-09-21 ("thực hiện sửa đi và merge"). Phạm vi mỗi FIX chỉ là file test ghi ở [4];
> mã sản phẩm của B0-01, B0-03, B0-05 không đổi. Nhánh mang nhiều prompt nên vào `main` bằng `--no-ff` (R-36).

---

## FIX-003 cho B0-01 — ba test của `case_gate` chốt trạng thái repo rỗng làm bất biến

**[1 TRIỆU CHỨNG]** `bash tools/verify/run.sh verify` bước 5 hỏng ngay khi B0-06 hợp nhất:

```
FAILED tools/tests/test_case_gate.py::test_real_operations_chưa_có_b0_06_trả_rỗng
FAILED tools/tests/test_case_gate.py::test_real_task_names - AssertionError: assert ['purge_expired_idempotency'] == []
FAILED tools/tests/test_case_gate.py::test_main_đạt_khi_chưa_có_thao_tác - assert 1 == 0
```

**[2 TÁI HIỆN]** Trên `feature/b0-06-api-framework` @ `eb40a3c`:
`pytest tools/tests/test_case_gate.py -k "real_operations or real_task_names or chưa_có_thao_tác"` → `3 failed`.

**[3 BẰNG CHỨNG]** `tools/tests/test_case_gate.py:472` `assert case_gate._real_operations() == []`;
`:478` `assert case_gate._real_task_names() == []`; `:485` `main() == 0` trong khi
`JUNIT_PATHS` bị trỏ đi nên `purge_expired_idempotency` báo thiếu `['J01','J06']`.
Ba khẳng định này trái CASE §2.3: `operations()` và `registered_tasks()` là **sổ thật của
tiến trình** và khác rỗng ngay khi có prompt đầu tiên mount route hay khai `@periodic`.

**[4 KHOANH VÙNG]** Sửa: `tools/tests/test_case_gate.py`. **Cấm sửa**: `tools/case_gate.py`
(logic cổng đúng, chỉ test sai), mọi file dưới `apps/`, `packages/`.

**[5 SỬA NHỎ NHẤT]** Dựng đầu vào tại chỗ thay vì đọc trạng thái repo: vắng mặt module dựng
bằng `sys.modules`, sổ task dựng bằng `monkeypatch`, `main()` chạy với `_real_operations`/
`_real_task_names` trả rỗng. Thêm một test khẳng định đường thật vẫn đọc được (`isinstance`),
ổn định với mọi số thao tác.

**[6 TEST CHẶN TÁI PHÁT]** `test_real_operations_khi_chủ_chưa_hợp_nhất_trả_rỗng`,
`test_real_operations_đọc_được_sổ_thật` — không khẳng định số lượng, nên prompt sau thêm route
không làm đỏ lại.

**[7 NGHIỆM THU]** `just verify` bước 1–6, 8 `đạt`; ba test đỏ → xanh.

---

## FIX-004 cho B0-03 — `test_new_revision` ghim head của cây revision làm hằng

**[1 TRIỆU CHỨNG]** `FAILED packages/db/tests/test_new_revision.py::test_creates_revision_with_charter_name`

**[2 TÁI HIỆN]** Trên cùng commit: `pytest packages/db/tests/test_new_revision.py -k charter_name` → `1 failed`.

**[3 BẰNG CHỨNG]** `packages/db/tests/test_new_revision.py:54`
`assert 'down_revision: str | None = "r20260920_b0_03"' in body`. BE-00 §6.1 cho **mỗi prompt
một revision**, nên head đổi sau mỗi lần hợp nhất; revision `r20260920_b0_06` của B0-06 là head
mới. Hằng này sẽ đỏ với B2-01, B2-03… y như vậy.

**[4 KHOANH VÙNG]** Sửa: `packages/db/tests/test_new_revision.py`. **Cấm sửa**:
`packages/db/new_revision.py` (hành vi đúng), `packages/db/migrations/**`.

**[5 SỬA NHỎ NHẤT]** Đọc head thật của bản sao cây revision bằng
`ScriptDirectory.from_config(...).get_heads()` **trước** khi tạo revision, rồi so với nó.

**[6 TEST CHẶN TÁI PHÁT]** Chính `test_creates_revision_with_charter_name` sau khi sửa: nó còn
khẳng định cây chỉ có **một** head (`assert len(heads) == 1`), nên hai head lọt vào cũng đỏ.

**[7 NGHIỆM THU]** `just verify` bước 6 `đạt` (`migrate_check` 9/9); test đỏ → xanh.

---

## FIX-005 cho B0-05 — hai test của `messaging` chốt "sổ task và beat rỗng"

**[1 TRIỆU CHỨNG]**

```
FAILED packages/messaging/tests/test_tasks.py::test_registered_tasks_leaves_out_tasks_declared_in_tests
FAILED packages/messaging/tests/test_worker_main.py::test_the_worker_process_is_ready_to_run_schedules
```

**[2 TÁI HIỆN]** `pytest packages/messaging/tests/test_tasks.py -k leaves_out`
và `pytest packages/messaging/tests/test_worker_main.py -k ready_to_run` → mỗi lệnh `1 failed`.

**[3 BẰNG CHỨNG]** `test_tasks.py:202` `assert registered_tasks() == []`;
`test_worker_main.py:56` `assert loaded["beat"] == []`. B0-06 khai
`@periodic("default.idempotency.purge_expired")` đúng bảng "Dọn rác" của BE-00 §7, dòng
"bản ghi idempotency hết hạn | B0-06". Mười lăm chủ khác trong bảng đó cũng sẽ khai lịch.

**[4 KHOANH VÙNG]** Sửa: `packages/messaging/tests/test_tasks.py`,
`packages/messaging/tests/test_worker_main.py`. **Cấm sửa**: `packages/messaging/tasks.py`,
`schedules.py`, `apps/worker/celery_main.py`.

**[5 SỬA NHỎ NHẤT]** Đổi khẳng định sang đúng bất biến mà docstring của hai test đã nói:
- sổ task **không chứa** task khai trong module test (thay cho "sổ rỗng");
- `app.conf.beat_schedule` của worker **bằng** sổ lịch dò lại **độc lập** trong cùng tiến trình
  con — `discover_jobs()` (idempotent) rồi `beat_schedule()` — thay cho "beat rỗng". Chứng minh
  "sổ được gắn đủ" mà không phụ thuộc số lịch.

**[6 TEST CHẶN TÁI PHÁT]** Hai test trên sau khi sửa: bỏ `discover_jobs()` khỏi `celery_main`
thì `beat` rỗng còn `beat_ledger` (dò lại độc lập) khác rỗng → đỏ; đưa task của module test vào sổ
→ đỏ.

> **Sửa lần hai (review 2026-09-21, finding #3).** Bản đầu tính `beat_ledger` bằng `beat_schedule()`
> **không** dò lại, nên khi `celery_main` quên `discover_jobs()` cả hai vế cùng rỗng và test vẫn qua —
> câu [6] ở trên khi đó là sai. Đã tái hiện: giả lập worker không dò → `beat = [] | beat_ledger = []`.
> Bản sửa gọi `discover_jobs()` trước khi tính vế phải; cùng giả lập đó nay cho
> `beat = [] ≠ beat_ledger = ['default.idempotency.purge_expired']`.

**[7 NGHIỆM THU]** `just verify` bước 5 `đạt`; hai test đỏ → xanh.

---

> **Giao việc FIX-006..FIX-028.** Người dùng yêu cầu ngày 2026-09-21: "thực hiện fix cho hết nợ đi".
> Mọi dòng `⬜` của `DEBT.md` sửa được bằng mã có một FIX; mỗi FIX sửa **đúng** file ở [4] của nó
> (ngoại lệ K27 do người điều phối giao). Ba nhánh chạy song song ở worktree riêng, theo chủ file:
> `fix/b0-01-gate-debts` (FIX-006..010), `fix/b0-04-storage-debts` (FIX-011..019),
> `fix/b0-05-messaging-debts` (FIX-020..027). FIX-028 nằm trên `feature/b0-07-contract-harness`
> vì cần `packages/testing/golden/recorder.py` của B0-07. Nhánh nhiều prompt vào `main` bằng `--no-ff`
> (R-36), mỗi nhánh qua `/merge-review` riêng (R-37).
> **Không có FIX:** NO-006, NO-021 (compose của app là deliverable của B0-08, prompt chưa chạy —
> sửa ở đây là viết việc của prompt khác); NO-018 (sửa là viết lại lịch sử đã được trỏ tới → chuyển `➖`).
>
> Luật chung cho mọi FIX dưới đây (FIX.md): test ở [6] **đỏ trên mã hiện tại trước khi sửa** (báo lệnh
> và mã thoát), không nới assert, không `skip`/`xfail`/retry để giấu (K24), không mock
> Postgres/Redis/MinIO (K23); không đổi hợp đồng HTTP; thấy lỗi khác thì ghi `DEBT.md`, không sửa.
> Dòng `DEBT.md` của nợ chuyển `✅` (hay `➖` kèm lý do đứng được) **trong chính commit sửa**.
> Nghiệm thu chung: `bash tools/verify/run.sh verify` thoát 0; commit
> `fix(<scope>): …` + trailer liền nhau `Prompt: <chủ>`, `Fix: FIX-<nnn>`, `Co-Authored-By: …` (R-36b).

## FIX-006 cho B0-01 — `_clean_dir` nuốt lỗi xoá (NO-008)

- **[1–3]** `tools/verify/steps.py:_clean_dir` gọi `shutil.rmtree(d, ignore_errors=True)`: file không xoá được bên trong thư mục ra bị bỏ qua, `merge-heads` có thể chép nhầm file cũ còn sót.
- **[4]** Sửa: `tools/verify/steps.py`, `tools/tests/test_steps*.py`.
- **[5]** Duyệt và xoá từng mục con của `d` (giữ lại chính mount point, FIX-001), để lỗi xoá nổi lên.
- **[6]** Test: mục con không xoá được → `_clean_dir` ném; mount point vẫn giữ được như test của FIX-001.

## FIX-007 cho B0-01 — `test_services` dùng trần bắt tay 5 s cho Postgres dùng chung (NO-042)

- **[1–3]** `tools/tests/test_services.py:32-33` `asyncpg.connect(..., timeout=5)` cho cả bản **đã dừng** lẫn bản **dùng chung**; chặng `host.docker.internal` kẹt thì bản dùng chung đỏ giả (`45a73ad`, bước 5 `1 failed`).
- **[4]** Sửa: `tools/tests/test_services.py`.
- **[5]** Bản đã dừng giữ trần ngắn (lỗi kết nối tới ngay); bản còn chạy dùng `GATE_CONNECT_TIMEOUT_S` của `packages.db.engine`.
- **[6]** Test hàm chọn trần: bản dừng → ngắn, bản chạy → `GATE_CONNECT_TIMEOUT_S`.

## FIX-008 cho B0-01 — mẫu golden không được chép ra `contract-samples/` (NO-043)

- **[1–3]** ENV §2: `CONTRACT_SAMPLES_DIR=/tmp/contract-samples` "cuối lượt chép ra `/src-out/contract-samples`"; `steps.py`/`in_container.sh` không chép, thư mục của worktree luôn rỗng.
- **[4]** Sửa: `tools/verify/steps.py`, `tools/tests/test_steps*.py`.
- **[5]** Sau `run_steps` của việc `verify` (kể cả khi có bước hỏng), chép nội dung `CONTRACT_SAMPLES_DIR` (nếu có) vào `OUT_DIR / "contract-samples"`; không xoá mount point.
- **[6]** Test: có mẫu → chép đủ cây; không có thư mục → không lỗi.

## FIX-009 cho B0-01 — chặng `host.docker.internal` kẹt ~68 s (NO-007)

- **[1–3]** NO-002, NO-036, NO-042: container verify nối testcontainers qua `TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal` (cổng chuyển tiếp qua máy Windows); thỉnh thoảng kẹt ~68 s.
- **[4]** Sửa: `deploy/compose/verify.yml`, `tools/verify/in_container.sh`, `tools/verify/run.sh`, test dưới `tools/tests/`.
- **[5]** Worker tự tìm, **tái hiện trước** (R-35): đo độ trễ bắt tay lặp nhiều lượt qua `host.docker.internal` và qua đường không đi qua máy Windows (gateway của mạng `bridge`, hay IP container trên cùng mạng). Chỉ đổi khi số đo chứng minh; CI (ngoài container, không đặt biến override) không được đổi hành vi.
- **[6]** Không tái hiện được trong số lượt đã hẹn: ghi vào `DEBT.md` số lượt, giả thuyết đã loại và bằng chứng; **không sửa mò**.

## FIX-010 cho B0-03 — `db_sessionmaker` dùng trần 10 s (NO-036)

- **[1–3]** `packages/testing/fixtures/db.py:109` dựng `DatabaseSettings(...)` với `db_connect_timeout_s` mặc định 10 s của đường request.
- **[4]** Sửa: `packages/testing/fixtures/db.py`, test dưới `packages/db/tests/`.
- **[5]** `db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S)` như `api_env` của B0-06.
- **[6]** Test: engine của `db_sessionmaker` mang trần bắt tay bằng `GATE_CONNECT_TIMEOUT_S`.

## FIX-011..FIX-019 cho B0-04 — `packages/storage` (NO-009..NO-017)

- **[4] chung:** Sửa `packages/storage/**` (mã + `tests/`). Cấm sửa file của prompt khác, kể cả `apps/api/files/`.
- **FIX-011 (NO-009):** `S3Error` có `response.status >= 500` → `DEPENDENCY_UNAVAILABLE` (503 + `Retry-After`); `AccessDenied`, `NoSuchBucket`… vẫn nổi lên. Test dùng MinIO **thật** đứng sau một proxy tiêm lỗi 5xx có thân XML (không mock MinIO, K23).
- **FIX-012 (NO-010):** `_delete_under` gom khoá qua `remove_objects` (≤ 1000/lượt), duyệt **và báo** mọi lỗi trả về. Test: xoá > 1 lô trên MinIO thật, đếm lượt gọi.
- **FIX-013 (NO-011):** `server_chosen_kind(key)` cho mọi khoá do server đặt tên sau khi đã kiểm magic bytes (ảnh đại diện, `…/pages/{i}.png`), vẫn cấm cho `original.<đuôi>`. Test: ký `inline` khoá trang không tốn `HEAD`; `original.png` vẫn phải đọc metadata.
- **FIX-014 (NO-012):** `delete_prefix` bản local: chỉ bỏ qua `FileNotFoundError`, lỗi khác qua `_disk_errors` → 503.
- **FIX-015 (NO-013):** `list_prefix` bơm theo lô, không `list(...)`/`sorted(rglob)` cả cây vào RAM (R-22); giữ thứ tự hợp đồng hiện có.
- **FIX-016 (NO-014):** tách bộ đổi lỗi đĩa lên `port.py`, `S3Storage.put` dùng chung (R-07): đĩa đầy khi đệm → 503.
- **FIX-017 (NO-015):** `ensure_bucket` chỉ nuốt `NotImplemented`; mã khác ghi `WARNING` kèm `code` hoặc ném.
- **FIX-018 (NO-016):** hai test lấy mốc từ `stat()` vừa đọc hoặc khẳng định quan hệ thứ tự, không trộn giờ thật với `fake_clock`.
- **FIX-019 (NO-017, phần B0-04):** finding #10 (khẳng định "không chứa khoá dạng thô") và #12 (chú thích `_message` ghi đúng bản tin 4 trường `k|e|d|n`). Phần B0-06 đã tuân (`eb40a3c`).

## FIX-020..FIX-027 cho B0-05 — `packages/messaging` (NO-022..NO-030)

- **[4] chung:** Sửa `packages/messaging/**` (mã + `tests/`). Không đổi tên task, hàng, payload.
- **FIX-020 (NO-022):** worker thật trong **tiến trình con** (`subprocess`), `SIGKILL` giữa task, khẳng định task được giao lại và lượt vượt trần thành `WORKER_LOST`.
- **FIX-021 (NO-023):** `INCR` + `EXPIRE` gộp một script Lua nguyên tử như `publish_once`.
- **FIX-022 (NO-024):** `worker_process_shutdown` đóng `Runner`; `reset_runner()` cho test.
- **FIX-023 (NO-025):** giới hạn là của `asyncio` (không ném được vào thân `@asynccontextmanager`): docstring của `hold` nêu người giữ khoá cho việc dài phải gọi `renew()` và kiểm giá trị; có test chứng minh `renew()` báo mất khoá. Nợ chuyển `➖` kèm lý do nếu không còn gì sửa được bằng mã.
- **FIX-024 (NO-027):** test khoá không đếm giờ thật với biên hẹp: khẳng định quan hệ (`EXISTS` trước/sau, token rào tăng) hoặc nới TTL lên vài giây.
- **FIX-025 (NO-028):** `release` trong `finally` bọc `try/except` ghi `WARNING` (TTL dọn hộ), không che ngoại lệ của thân. Test theo công thức tái hiện ghi ở NO-028.
- **FIX-026 (NO-029):** ghi ngưỡng + đường nâng cấp cạnh `FENCE_SUFFIX` (R-05) và ràng buộc bàn giao cho B6-03a; nợ chuyển `➖` nếu hiến chương vẫn cho phép.
- **FIX-027 (NO-030):** `_fail` chỉ ghi `type(exc).__name__` + ≤ 200 ký tự đầu của thông điệp.

## FIX-028 cho B0-06 — hai bộ khớp (method, đường) → thao tác (NO-044)

- **[1–3]** `packages/testing/fixtures/api.py:_op_matchers/operation_of` trùng việc với `packages/testing/golden/recorder.py:operation_resolver` (R-07).
- **[4]** Sửa: `packages/testing/fixtures/api.py`, test ở `packages/testing/golden/tests/test_recorder.py` (trên nhánh B0-07).
- **[5]** `operation_of` trả `.op` của `recorder.resolve_operation(method, path)`; xoá `_op_matchers`.
- **[6]** Test hiện có của `trace_case` (`apps/api/core/tests/test_fixtures.py`) giữ nguyên và xanh; thêm test khẳng định vết case và bộ ghi golden khớp **cùng** thao tác cho một request.

## FIX-029 cho B0-06 — năm test lõi chốt trạng thái "chưa có B1-01" (NO-053)

> Giao trong phiên B1-01 (ngoại lệ của K27, như FIX-003..005): người điều phối chọn "FIX here" ngày 2026-09-21
> khi cổng bước 5 của B1-01 đỏ vì chúng. Chỉ sửa file test ở [4]; mã sản phẩm của B0-06 không đổi.

- **[1 TRIỆU CHỨNG]** `bash tools/verify/run.sh verify` trên `feature/b1-01-auth-login-sessions` @ `4320e0e`, bước 5 `hỏng`:
  `test_app.py::test_deny_all_when_no_auth_module`, `::test_production_without_auth_module_refuses_to_start`,
  `::test_verifier_module_exists_is_false_today`, `::test_discover_routers_finds_real_modules`,
  `test_openapi.py::test_real_app_has_exactly_three_operations` (`5 failed, 1400 passed`).
- **[2 TÁI HIỆN]** `pytest apps/api/core/tests/test_app.py apps/api/core/tests/test_openapi.py` @ `4320e0e` → `5 failed, 38 passed`.
- **[3 BẰNG CHỨNG]** Các test đọc trạng thái repo làm bất biến: `_verifier_module_exists() is False`, `discover_routers() == [files, health]`,
  `operations() == ("files_read_object", "health_live", "health_ready")`; B1-01 thêm `apps/api/auth/verifier.py` và `router.py` theo đúng BE-00 §2.2.
- **[4 KHOANH VÙNG]** Sửa: `apps/api/core/tests/test_app.py`, `apps/api/core/tests/test_openapi.py`. Cấm: `apps/api/core/*.py`.
- **[5 SỬA NHỎ NHẤT]** Dựng đầu vào tại chỗ: vắng module auth bằng `monkeypatch` `_verifier_module_exists`/`importlib.util.find_spec`
  (gói cha thiếu và chỉ thiếu `verifier`); dò router so với `apps/api/*/router.py` trên đĩa; ba route lõi có mặt và công khai, mọi route công khai
  `idempotency == "off"` — không ghim tổng số.
- **[6 TEST CHẶN TÁI PHÁT]** Chính năm test đã viết lại (một test thành hai tham số). Đỏ 5/5 trước (`5 failed, 38 passed`), xanh sau (`44 passed`).
- **[7 NGHIỆM THU]** Bảng cổng của báo cáo B1-01; commit `test(api): …` + `Prompt: B0-06`, `Fix: FIX-029`.

## FIX-030, FIX-031 cho B0-06 — hạn mức đọc lười, DB an toàn sạch giữa các test (NO-054, NO-055)

> Giao trong phiên B1-01 như FIX-029: người điều phối yêu cầu "fix nợ" ngày 2026-09-21. Chỉ sửa file ở [4].

- **FIX-030 (NO-054).** [1–3] `apps/api/core/ratelimit.py:rate_limit` so `limit < 1` lúc khai, nên hạn mức đọc từ
  `AuthSettings` (lười: B0-06 nhập mọi module khi chưa có biến môi trường, test nâng hạn mức bằng `setenv`) buộc
  `apps/api/auth/router.py` dựng limiter mỗi request. [4] Sửa `apps/api/core/ratelimit.py`, `apps/api/core/tests/test_ratelimit.py`;
  cấm đổi hành vi của hạn mức số. [5] `limit`/`window_s` nhận `int | Callable[[], int]`: số kiểm lúc khai như cũ, hàm gọi
  và kiểm mỗi lượt. [6] `test_quota_can_be_read_at_request_time`, `test_lazy_quota_below_one_fails_at_request_time`:
  đỏ trước (`TypeError: '<' not supported between instances of 'function' and 'int'`), xanh sau.
- **FIX-031 (NO-055).** [1–3] `packages/testing/fixtures/api.py:api_env` phụ thuộc `cache_client` mà không phụ thuộc
  `safe_client`: bộ đếm `store="safe"` và khoá đăng nhập (mọi lượt ASGI từ `127.0.0.1`) rò sang test sau. [4] Sửa
  `packages/testing/fixtures/api.py`, `apps/api/core/tests/test_fixtures.py`. [5] `api_env` nhận thêm `safe_client`
  (`FLUSHDB` lúc dọn). [6] `test_api_env_flushes_both_redis_roles`: đỏ trước (thiếu `safe_client`), xanh sau.
- **[7]** Bảng cổng của báo cáo B1-01; mỗi FIX một commit `Prompt: B0-06` + `Fix: FIX-<nnn>`. Phía B1-01 (commit riêng,
  `Prompt: B1-01`): khai `_login_ip_limit`, `_refresh_total_limit` một lần bằng hàm hạn mức; `auth_app`/`probe_app`
  bỏ `FLUSHDB` thừa.

---

> **Giao việc FIX-032..FIX-037 và hợp nhất FIX-006..FIX-027.** Người dùng yêu cầu ngày 2026-09-22: "đọc DEBT.md và fix
> tất cả các nợ". Ba nhánh của đợt trước (`fix/b0-01-gate-debts`, `fix/b0-04-storage-debts`, `fix/b0-05-messaging-debts`)
> chưa từng qua `/merge-review`: mỗi nhánh **gộp `main` vào** (không rebase — giữ sha FIX-006..027 đã ghi ở bảng trên),
> chạy lại cổng, rồi qua review riêng. FIX mới chạy song song ở worktree riêng, theo vùng file (ngoại lệ K27 do người
> điều phối giao, như FIX-003..005): FIX-032 trên `fix/b0-01-gate-debts` (cùng `tools/verify/steps.py` với FIX-006, 008);
> FIX-033..035 trên `fix/b0-07-contract-tool-debts`; FIX-036, 037 trên `fix/b0-03-check-constraint-names` (phải vào
> cùng nhau: FIX-036 làm bước 6 đỏ trên `main` cho tới khi FIX-037 đổi tên). Người điều phối cho phép FIX-037 thêm tên
> revision của nó vào `docs/contracts.toml` (BE-00 §6.1).
> **Không có FIX:** NO-006, NO-021 (compose của app, deliverable của B0-08, prompt chưa chạy); NO-050 (hiến chương,
> người điều phối sửa sau khi FIX-009 vào `main`); NO-051 (ràng buộc bàn giao cho job CI của B0-09, prompt chưa chạy).
>
> Luật chung như đợt FIX-006..028 (đoạn giao việc ở trên): test [6] đỏ trước, xanh sau; không nới assert, không
> `skip`/`xfail`/retry (K24), không mock dịch vụ (K23), không đổi hợp đồng HTTP; dòng `DEBT.md` chuyển `✅` trong chính
> commit sửa; commit `fix(<scope>): …` + trailer liền nhau `Prompt: <chủ>`, `Fix: FIX-<nnn>`, `Co-Authored-By: …`.

## FIX-032 cho B0-01 — lượt verify lạnh tải `npm` trong bước 5 (NO-048)

- **[1–3]** Volume chưa có `$CONTRACT_NODE_DIR/<băm package-lock>`: fixture phiên `contract_build`
  (`packages/testing/fixtures/golden.py:47`) gọi `build_layout` → `ensure_node_modules` → `npm ci` từ `registry.npmjs.org`
  ngay trong pytest của bước 5 (bước 5 chạy trước bước 7). Trái "không tải mạng trong test".
- **[4]** Sửa: `tools/verify/steps.py` (hoặc `tools/verify/in_container.sh`), test dưới `tools/tests/`. Cấm sửa
  `tools/contract/**`, `packages/testing/**`.
- **[5]** Việc `verify` làm ấm `node_modules` ở pha chuẩn bị, **trước** bước 5: gọi
  `tools.contract.runner_client.ensure_node_modules(<đúng thư mục mà contract_build dùng>)`; lỗi làm ấm là lỗi hạ tầng của
  cổng, báo rõ, không nuốt. Không chạy khi `--steps` không gồm bước cần runner Node.
- **[6]** Test: chuỗi việc của `verify` gọi làm ấm trước bước 5 (theo lối `tools/tests/test_steps_commands.py`).

## FIX-033, FIX-034 cho B0-01, B0-07 — bộ ghi golden nhập tên riêng của `case_gate` (NO-049)

- **[1–3]** `packages/testing/golden/recorder.py:32` `from tools.case_gate import _TEST_COMMON_RE, _TEST_OP_CASE_RE`;
  B0-01 đổi tên hai hằng thì mọi phiên test hỏng lúc nhập (`packages/testing/fixtures/api.py` nhập `recorder`).
- **[4]** FIX-033 (`Prompt: B0-01`): `tools/case_gate.py`, `tools/tests/test_case_gate.py`. FIX-034 (`Prompt: B0-07`):
  `packages/testing/golden/recorder.py` và test của nó. Hai commit riêng.
- **[5]** `case_gate` xuất một hàm công khai tách tên test (mẫu chung xét trước mẫu riêng, như chính `case_gate`), và dùng
  lại nó ở chỗ của mình (R-07); bộ ghi gọi hàm đó. Hành vi tách tên không đổi.
- **[6]** Test hàm công khai (dạng riêng, dạng chung, tên không khớp); test chặn bộ ghi nhập tên `_…` của `case_gate`.

## FIX-035 cho B0-07 — `tools.contract.check` để lại thư mục dựng tạm (NO-052)

- **[1–3]** `tools/contract/check.py:main` không có `--build-dir` dựng vào `tempfile.mkdtemp()` và không dọn: mỗi lượt để
  lại ≈ 16 MB bản chép `src` của AppFront.
- **[4]** Sửa: `tools/contract/check.py`, `tools/contract/tests/test_check.py`.
- **[5]** Không `--build-dir` → `tempfile.TemporaryDirectory(prefix="contract-")`; có `--build-dir` → giữ lại để gỡ lỗi.
- **[6]** Test: `main` không `--build-dir` (thư mục tạm trỏ về `tmp_path`) không để lại `contract-*`.

## FIX-036, FIX-037 cho B0-03, B0-06 — tên `CHECK` lặp tiền tố (NO-057)

- **[1–3]** `r20260920_b0_06_idempotency.py:44-45` truyền `name=f"ck_{TABLE}_…"`; quy ước
  `ck_%(table_name)s_%(constraint_name)s` (`packages/db/base.py:17`) áp thêm lần nữa → DB có
  `ck_idempotency_records_ck_idempotency_records_state`, `…_key_format`, model sinh `ck_idempotency_records_state`.
  `migrate_check` "model khớp DB" (`compare_metadata`) không so tên `CHECK`, nên cổng không bắt.
- **[4]** FIX-036 (`Prompt: B0-03`): `packages/db/migrate_check.py`, `packages/db/tests/`. FIX-037 (`Prompt: B0-06`): một
  revision contract mới dưới `packages/db/migrations/versions/` (tạo bằng `python -m packages.db.new_revision`), dòng tên
  revision trong `docs/contracts.toml`. Cấm sửa revision đã hợp nhất (`r20260920_b0_06_idempotency.py`).
- **[5]** FIX-036: bước "model khớp DB" (hoặc bước ngay sau) so tập tên `CHECK` của mọi bảng trong `Base.metadata` (tên đã
  áp quy ước) với `pg_constraint` (`contype = 'c'`, chỉ bảng của metadata); lệch → bước hỏng, in tên lệch. FIX-037:
  revision `r20260921_b0_06_fix037 (tên `new_revision` sinh theo ngày UTC)` mang `# contract:` ở đầu, `upgrade` đổi tên hai ràng buộc về tên của model,
  `downgrade` đổi ngược.
- **[6]** Test FIX-036: DB có `CHECK` tên lặp tiền tố → bước hỏng (đỏ trước: bước đạt). Cổng bước 6 đỏ khi chỉ có
  FIX-036, xanh khi có cả FIX-037.

## FIX-038 cho B0-01 — `lint_migrations` chặn cả revision contract đã đăng ký (NO-058)

> Phát hiện trong FIX-037 (worker hỏi, người điều phối chọn sửa gốc ngày 2026-09-22). Cùng nhánh
> `fix/b0-03-check-constraint-names`, commit trước FIX-037.

- **[1–3]** `tools/lint_migrations.py:_lint_file` luôn gọi `_lint_body`: revision mang `# contract:` và đã có trong
  `docs/contracts.toml` vẫn bị báo "execute chuỗi SQL cấm" với `RENAME`/`DROP`, nên đường revision contract của
  BE-00 §6.1 không dùng được (FIX-037 cần `RENAME CONSTRAINT`).
- **[4]** Sửa: `tools/lint_migrations.py`, `tools/tests/test_lint_migrations*.py`.
- **[5]** Contract đã đăng ký chỉ được miễn các luật **phá huỷ** của expand (`drop_*`, `rename_table`, `alter_column`
  đổi tên/`nullable=False`/`type_`, chuỗi SQL `DROP|RENAME|SET NOT NULL|TRUNCATE|DELETE FROM|ALTER COLUMN … TYPE`,
  `add_column` NOT NULL không default). Vẫn kiểm: `execute`/`text`/`exec_driver_sql` với đối số không phải hằng,
  `batch_alter_table`, `create_index` thiếu `CONCURRENTLY`/ngoài `autocommit_block`, tên revision. Chưa đăng ký → như cũ.
- **[6]** Contract đã đăng ký có `RENAME`/`DROP` → đạt (đỏ trước); có `execute` chuỗi không hằng → vẫn hỏng; chưa đăng
  ký có `RENAME` → hỏng.

---

> **Giao việc FIX-039..FIX-051 (đợt 2).** Người dùng yêu cầu ngày 2026-09-22: "thực hiện fix tiếp, dùng orca, mỗi session 12 nợ
> kỹ thuật cho đến khi fix hết trong debt.md". Đợt 1 (FIX-006..038) đã vào `main` qua năm nhánh `fix/*`, mỗi nhánh một phiên
> `/merge-review` riêng. Đợt 2 nhận đúng 12 nợ còn sửa được: mười nợ mã dưới đây (NO-060, NO-065..NO-070, NO-072..NO-074) và hai
> dòng hiến chương của người điều phối (NO-050, NO-071 — người điều phối tự làm, không có FIX). Bốn worktree chạy song song theo
> vùng file (ngoại lệ K27 do người điều phối giao, như đợt 1), trần 2 lượt verify cùng lúc trên máy (RAM):
> `fix/b0-03-migration-tool-debts` (FIX-039..042), `fix/b0-04-object-key-debts` (FIX-043..047),
> `fix/b1-01-parallel-refresh-flake` (FIX-048), `fix/b0-05-quiet-release-case-filter` (FIX-049..051).
> **Không có FIX (chủ là prompt chưa chạy):** NO-006, NO-021, NO-062 (B0-08, `deploy/**`); NO-051 (job CI của B0-09);
> NO-061 (B6-01, checksum bản gốc seed); NO-063 (B5-04, ràng buộc bàn giao).
>
> Luật chung như đợt 1: test [6] đỏ trước, xanh sau; không nới assert, không `skip`/`xfail`/retry (K24), không mock dịch vụ
> (K23), không đổi hợp đồng HTTP; dòng `DEBT.md` chuyển `✅` trong chính commit sửa; commit `fix(<scope>): …` (hoặc
> `refactor(...)`/`test(...)` khi đúng loại) + trailer liền nhau `Prompt: <chủ>`, `Fix: FIX-<nnn>`, `Co-Authored-By: …`.

## FIX-039 cho B0-03 — `test_new_revision` đóng băng ngày lúc nhập (NO-065)

- **[1–3]** `packages/db/tests/test_new_revision.py` tính `TODAY = datetime.now(UTC)…` một lần lúc nhập; `new_revision.main`
  đọc `datetime.now(UTC)` lúc gọi (`packages/db/new_revision.py:66`). Bộ test vắt qua nửa đêm UTC → glob `r{TODAY}_…` rỗng,
  `test_creates_revision_with_charter_name`, `test_fix_revision_allowed_once` đỏ (`F.F` ở bước 5, `fix/b0-05-messaging-debts`
  @ `f4223f2`; tái hiện bằng lùi `TODAY` một ngày: `2 failed, 11 passed`).
- **[4]** Sửa: `packages/db/new_revision.py`, `packages/db/tests/test_new_revision.py`. Cấm: revision đã có, `tools/**`.
- **[5]** `new_revision` nhận ngày qua `Clock` của `packages/core/clock.py` (R-18; `main(argv, clock=SystemClock())` hoặc
  tương đương), test ghim bằng `fake_clock`. Không nới assert.
- **[6]** Test đặt đồng hồ giả qua nửa đêm giữa lúc dựng kỳ vọng và lúc gọi → tên revision theo ngày của đồng hồ tiêm vào; đỏ
  trên mã hiện tại.

## FIX-040 cho B0-03 — `run_checks` vượt R-08 (NO-069)

- **[1–3]** `packages/db/migrate_check.py:run_checks` 82 dòng, CC 13 (review `fix/b0-03-check-constraint-names` finding #1).
- **[4]** Sửa: `packages/db/migrate_check.py`, `packages/db/tests/test_migrate_check.py`.
- **[5]** Đưa từng bước lên mức module (nhận `engine`/`config`/`target` qua tham số), `run_checks` chỉ còn vòng lặp và dọn
  engine. Hành vi, tên bước, thứ tự bước, mã thoát không đổi.
- **[6]** Tái cấu trúc thuần: không có test đỏ; bằng chứng là `packages/db/tests` xanh trước và sau với cùng số test, và số
  dòng/CC mới của hàm ghi trong báo cáo (R-08).

## FIX-041 cho B0-03 — bước "tên CHECK khớp model" đỏ giả với CHECK gắn kiểu (NO-070)

- **[1–3]** `_check_name_drift` lấy mọi `CheckConstraint` của bảng. `Boolean(create_constraint=True)` làm bước ném
  `InvalidRequestError`; `Enum(…, create_constraint=True)` native làm bước báo "thiếu trong DB" (probe của review trên
  postgres:16-alpine). Chưa model nào dùng.
- **[4]** Sửa: `packages/db/migrate_check.py`, `packages/db/tests/test_migrate_check.py`.
- **[5]** Bỏ các ràng buộc mà DDL của dialect không phát ra (`_create_rule` trả `False` với DDL compiler), comment ghi ngưỡng
  vì dùng API riêng của SQLAlchemy (R-05). Không đổi cách so với CHECK mức bảng.
- **[6]** Metadata thử có `Boolean(create_constraint=True)` và `Enum(..., create_constraint=True)` → bước đạt (đỏ trước: ném /
  báo thiếu); CHECK mức bảng lệch tên vẫn hỏng.

## FIX-042 cho B0-01 — `_lint_body` vượt R-08 (NO-068)

- **[1–3]** `tools/lint_migrations.py:_lint_body` 78 dòng, CC 28, 25 nhánh; phân loại "phá huỷ hay không" giấu trong vòng lặp
  (`_BANNED_CALL_NAMES` trộn bốn thao tác phá huỷ với `batch_alter_table`, một `Report()` dùng để bỏ đi) — review
  `fix/b0-03-check-constraint-names` finding #1, #4.
- **[4]** Sửa: `tools/lint_migrations.py`, `tools/tests/test_lint_migrations*.py`.
- **[5]** Mỗi luật một hàm `_check_<luật>(node, …)`; hằng `_DESTRUCTIVE_CALL_NAMES` tách khỏi `batch_alter_table`; bỏ `Report()`
  dùng một lần. Hành vi (thông báo, luật miễn cho contract đã đăng ký của FIX-038) không đổi.
- **[6]** Tái cấu trúc thuần: `tools/tests/test_lint_migrations*.py` xanh trước/sau cùng số test; thêm một test chốt rằng tên
  thêm vào `_DESTRUCTIVE_CALL_NAMES` được miễn cho contract còn `batch_alter_table` thì không.

## FIX-043 cho B0-02, FIX-044 cho B0-04, FIX-045 cho B5-01 — luật khoá object có hai nguồn (NO-060)

- **[1–3]** `packages/ml_contracts/payloads.py:check_object_key` chép luật khoá của `packages/storage/keys.py:check_key`
  (`ml_contracts` không được nhập `storage`, [9] B5-01); test `test_check_object_key_matches_storage_rules` giữ hai bản khớp.
- **[4]** FIX-043: module mới dưới `packages/core/` (vd `object_keys.py`) + test dưới `packages/core/tests/`. FIX-044:
  `packages/storage/keys.py` + test của `packages/storage`. FIX-045: `packages/ml_contracts/payloads.py` + test của
  `packages/ml_contracts`. Cấm `.importlinter`.
- **[5]** Dời `check_key`/`check_prefix` (và hằng `MAX_KEY_BYTES`, đuôi metadata, `_SEGMENT_RE`) xuống `packages/core`;
  `storage` và `ml_contracts` cùng nhập, xoá bản chép (cả `payloads._prefix_key`). Vẫn ném `ValueError`; thông báo theo bản
  của `storage` (test nào của `ml_contracts` chốt chuỗi cũ thì đổi theo, ghi rõ). `packages/core` không thêm thư viện (BE-00 §13.1).
- **[6]** Test cũ khớp hai bản đổi thành test một nguồn: `payloads.check_object_key is object_keys.check_key` (hoặc gọi thẳng),
  đỏ trên mã hiện tại; bộ 12 mẫu biên chuyển về test của `packages/core`.

## FIX-046 cho B0-04 — `_SERVER_NAMED_RE` chép luật id tầng (NO-073)

- **[1–3]** `packages/storage/keys.py:30-34` chép tay `L-[0-9A-Z]{10,64}` của `packages/core/ids.py:60` (`is_spatial_id`).
- **[4]** Sửa: `packages/storage/keys.py` + test của `packages/storage`.
- **[5]** Tách khoá theo `/` và kiểm từng đoạn bằng `is_id`/`is_spatial_id` như hàm dựng khoá; bỏ regex chép.
- **[6]** Test khoá trang với id tầng dài 10 và 64 (đạt), 9 và 65 (không phải khoá do server đặt) và một id tầng mà luật của
  `core/ids.py` chấp nhận nhưng regex cũ từ chối (hoặc ngược lại) → đỏ trước; nếu hai luật trùng khít trên mọi mẫu thì test
  chốt một nguồn (đột biến luật ở `core` làm test storage đỏ), ghi rõ trong báo cáo.

## FIX-047 cho B0-04 — test FIX-012 không chạm biên lô (NO-072)

- **[1–3]** `packages/storage/tests/test_s3.py:186` `test_delete_prefix_deletes_in_batches` chỉ ghi 3 object; spec FIX-012 [6]
  đòi "xoá > 1 lô".
- **[4]** Sửa: `packages/storage/tests/test_s3.py`.
- **[5]** 1001 object ghi song song (có trần đồng thời), khẳng định đúng 2 lượt `POST ?delete`, 0 `DELETE`, tiền tố rỗng.
- **[6]** Test mới đỏ trên bản `_delete_under` trước FIX-012 (xoá từng object: 1001 `DELETE`) — dựng lại bản cũ trong `.cache/`.

## FIX-048 cho B1-01 — `test_auth_refresh__C11_parallel` chập chờn (NO-066)

- **[1–3]** Cổng bước 5 trên `fix/b0-05-messaging-debts` @ `22dee96`: `At index 20 diff: 401 != 429` (≥ 21 lượt 401 thay vì
  `REFRESH_FAIL_LIMIT` = 20). Không tái hiện trong 14 lượt. Giả thuyết: `soft_redis(bump…)` trả `None` (Redis chậm quá
  `CONNECT_TIMEOUT_S` = 2 s qua proxy cổng dưới tải) → lượt đó không đếm.
- **[4]** Sửa: `apps/api/auth/tests/test_refresh.py`; `apps/api/auth/router.py` chỉ khi gốc nằm ở đó. Cấm `packages/**`.
- **[5]** Tái hiện trước (R-35): chạy test dưới `coverage` nhiều lượt, song song tải CPU/verify khác; bắt log `rate_limit_open`.
  Gốc là Redis hỏng → test phải báo đúng tên nguyên nhân (không thành "đếm sai"), hoặc sửa đường đếm nếu gốc là mã. Không nới
  assert, không retry.
- **[6]** Test đỏ tất định dựng lại đúng điều kiện gốc (vd kết nối bị treo quá trần ở đúng một lượt), xanh sau sửa. Không tái
  hiện được sau số lượt đủ lớn → ghi `DEBT.md` số lượt, giả thuyết đã loại trừ và bằng chứng (R-35), `worker_done --outcome failed`.

## FIX-049 cho B0-01 — bộ lọc của `_found_cases_by_op` chưa test nào chạm (NO-067)

- **[1–3]** `tools/case_gate.py:347-348`: dòng `continue` chưa chạy lần nào; đột biến bỏ bộ lọc case chung vẫn `58 passed`
  (review `fix/b0-07-contract-tool-debts` finding #1).
- **[4]** Sửa: `tools/tests/test_case_gate.py`.
- **[5]** Test `evaluate` với `test_common__C01[x_create]` và `test_x_create_is_public` (`passed`, có vết `op="x_create"`,
  status 200) → `"C01"` không vào `found` của `x_create` và không vào case chung.
- **[6]** Đỏ trên `case_gate.py` đã đột biến (bỏ vế lọc) — ghi lệnh; xanh trên mã hiện tại.

## FIX-050 cho B0-05, FIX-051 cho B5-01 — trả khoá lặng lẽ có hai bản (NO-074)

- **[1–3]** "Trả khoá; Redis hỏng thì `WARNING` rồi bỏ qua (TTL dọn hộ), không che lỗi của thân" có ở
  `packages/messaging/locks.py:103` (`SafeLock._release_quietly`, riêng tư) và `apps/ml/runtime/gpu.py:129`
  (`_Keeper._release`).
- **[4]** FIX-050: `packages/messaging/locks.py` + test của `packages/messaging`. FIX-051: `apps/ml/runtime/gpu.py` + test của
  `apps/ml/runtime`.
- **[5]** B0-05 công khai `release_quietly(token)` (docstring nói rõ khi nào dùng thay `release`); B5-01 gọi
  `runner.run(lock.release_quietly(token))`, xoá bản chép. Tên sự kiện log giữ như test hiện có đòi hỏi, hoặc ghi rõ đổi.
- **[6]** Test B5-01: Redis hỏng lúc trả khoá GPU → một `WARNING` từ đúng một nguồn, thân không bị che; test chốt `gpu.py` không
  còn tự bắt lỗi trả khoá (AST hoặc đột biến) — đỏ trên mã hiện tại.

---

> **Giao việc FIX-052..FIX-059 (đợt 3).** Tiếp yêu cầu ngày 2026-09-22 ("mỗi session 12 nợ … cho đến khi fix hết"). Đợt 3 nhận
> các nợ mã do đợt 2 và các phiên review đợt 2 tìm ra: NO-075, NO-076, NO-077, NO-078, NO-080. Hai worktree:
> `fix/b0-04-key-layout-debts` (FIX-054..058, NO-076, NO-077) chạy ngay; `fix/b0-01-gate-log-debts` (FIX-052, 053, 059,
> NO-075, NO-078, NO-080) chạy sau khi `fix/b1-01-parallel-refresh-flake` (dòng NO-078) và `fix/b0-03-migration-tool-debts`
> (dòng NO-080) vào `main`. **Không có FIX:** NO-079 cùng NO-050, NO-071 (hiến chương/prompt — người điều phối, chờ người
> dùng quyết nơi sửa). Luật chung như đợt 1–2; trần 2 lượt verify cùng lúc.

## FIX-052 cho B0-01 — chép mẫu golden hỏng thì mất bảng cổng (NO-075)

- **[1–3]** `tools/verify/steps.py:267` `export_contract_samples()` chạy trước `_print_table` và không bắt lỗi: thư mục ra thiếu
  hay không ghi được → traceback, không có bảng, lượt 8/8 đạt vẫn thoát 1 (probe review: `VERIFY_OUT_DIR=/proc/rv`).
- **[4]** Sửa: `tools/verify/steps.py`, `tools/tests/test_steps*.py`.
- **[5]** In bảng trước; lỗi `OSError` khi chép mẫu → một dòng lỗi rõ ra stderr (hoặc một dòng bảng "chép mẫu golden") và
  thoát 1. Không nuốt lỗi.
- **[6]** Test `VERIFY_OUT_DIR` không ghi được → bảng vẫn in đủ, có dòng lỗi chép mẫu, mã thoát 1; đỏ trên mã hiện tại.

## FIX-053 cho B0-01 — log cổng mất khi shell bọc bị cắt (NO-080)

- **[1–3]** Container `verify-run` AutoRemove, output chỉ đi qua stdout của client `docker compose run`; client chết → log
  bước 4–8 mất, chỉ còn mã thoát qua `docker wait` (W6-DBTOOLS, `e5d0247`).
- **[4]** Sửa: `tools/verify/in_container.sh` và/hoặc `tools/verify/steps.py`, `tools/verify/run.sh`; test dưới `tools/tests/`.
  Không đổi `deploy/compose/verify.yml` trừ khi cần mount mới (ghi lý do).
- **[5]** Toàn bộ output của lượt (bảng cổng, tóm tắt pytest, `coverage_gate`) đồng thời ghi ra file dưới thư mục mount host
  (`/src-out/…` → `.cache/src-out/…` của worktree), sống sót khi client compose chết; `run.sh` in đường dẫn file lúc bắt đầu.
- **[6]** Test: sau một lượt `verify` giả (bước rỗng/nhanh), file log trên thư mục ra có bảng cổng và mã thoát; đỏ trên mã hiện
  tại (không có file).

## FIX-054 cho B0-02, FIX-055 cho B0-04 — thân ULID có hai nguồn (NO-076)

- **[1–3]** `packages/storage/keys.py:26` `_ULID_RE` chép thân ULID của `packages/core/ids.py:35` `_ULID_BODY` (ảnh đại diện
  dùng ULID trần không tiền tố; `core/ids.py` chỉ phơi `is_id(prefix, value)`).
- **[4]** FIX-054: `packages/core/ids.py` + test của `packages/core`. FIX-055: `packages/storage/keys.py` + test của
  `packages/storage`.
- **[5]** B0-02 phơi hàm kiểm thân ULID không tiền tố (vd `is_ulid(value)`), `is_id` dùng lại nó; B0-04 dùng trong `avatar`,
  xoá `_ULID_RE`.
- **[6]** Test một nguồn (đột biến `_ULID_BODY` làm test storage đỏ, hoặc `keys` không còn hằng regex ULID) — đỏ trên mã hiện tại.

## FIX-056 cho B0-02, FIX-057 cho B0-04, FIX-058 cho B5-01 — bố cục tiền tố lượt tải lên có hai nguồn (NO-077)

- **[1–3]** `packages/ml_contracts/payloads.py:115` `_upload_prefix` dựng lại `projects/{prj}/floors/{L-…}/uploads/{upl}/` của
  `packages/storage/keys.py:64` `upload_prefix` (`ml_contracts` không được nhập `storage`).
- **[4]** FIX-056: `packages/core/object_keys.py` + test. FIX-057: `packages/storage/keys.py` + test. FIX-058:
  `packages/ml_contracts/payloads.py` + test.
- **[5]** Dời phần bố cục dùng chung (tiền tố lượt tải lên, dựng từ id đã kiểm) xuống `packages/core/object_keys.py`; `storage`
  và `ml_contracts` cùng gọi, xoá bản dựng lại. Nếu dời làm `core` phải biết quá nhiều về bố cục của `storage` (vd kéo theo
  mọi hàm dựng khoá), dừng và `ask` — phương án khác là `➖` kèm lý do.
- **[6]** Test một nguồn cho tiền tố lượt tải lên, đỏ trên mã hiện tại.

## FIX-059 cho B0-05 — worker Celery thử để logger gốc ở ERROR (NO-078)

- **[1–3]** `packages/testing/fixtures/messaging.py:149` `start_worker(...)` dùng `loglevel` mặc định `"error"`; `app.log.setup`
  chiếm logger gốc (thay handler, đặt mức 40) và không trả lại → `WARNING` của test chạy sau không vào báo cáo đỏ.
- **[4]** Sửa: `packages/testing/fixtures/messaging.py` + test của fixture (dưới `packages/testing/` hay `packages/messaging/tests/`).
- **[5]** Fixture không để lại dấu trên logger gốc: `worker_hijack_root_logger=False` cho app thử, hoặc lưu mức + handler rồi
  trả lại khi worker dừng.
- **[6]** Test: mức và handler của logger gốc trước và sau fixture worker bằng nhau; đỏ trên mã hiện tại.
