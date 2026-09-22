# Review merge fix/b0-01-gate-debts → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập**. Tôi không viết mã của nhánh; mọi khẳng định trong commit, `DEBT.md` và báo cáo tác giả (`W3-GATE.report.md`) đều đã tự kiểm lại · Commit đầu nhánh: `22c259b66de6`.
- Phạm vi: `git diff 7ba37ae...22c259b`, 11 commit.
  - 9 commit thường: `e3f2598` FIX-010 (`Prompt: B0-03`); `f3559f1` FIX-007, `a61b92c` FIX-006, `d1c72d5` FIX-008, `3ca1463` FIX-009, `eea1a43`/`804f31e` (sổ nợ NO-050/051), `02f2b64` FIX-032, `caaf5ab` FIX-009 bổ sung (đều `Prompt: B0-01`).
  - 2 commit gộp `main`: `900494a`, `22c259b`.
  - Diff: 8 file, +330/−35. Mã sản phẩm +88/−18 (`tools/verify/steps.py`, `packages/testing/fixtures/{services,db}.py`, `deploy/compose/verify.yml`), test +234.
  - **`main` đã đi tiếp trong lúc review:** `7ba37ae` → `1a059d6` (gộp `fix/b0-03-check-constraint-names`, `fix/b0-04-storage-debts`, 16 commit). Xem "Hợp nhất với `main`" bên dưới.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**.
  - Chạy tại chỗ trong worktree sạch, 02:56:54Z → 03:03:12Z. Lúc bắt đầu có 1 `verify-run` khác (< 2).
  - Mã thoát lấy thẳng từ `$?` của shell bọc (không bị cắt, không cần `docker wait`).
  - Log: `C:/Users/mxuan/AppData/Local/Temp/claude/C--Users-mxuan-orca-workspaces-appback-fix-gate/5b9b36b3-12b8-443c-888b-2e4e92524081/scratchpad/gate.verify.log`.
  - Kết quả: `1982 passed, 10 skipped, 1 deselected` trong 293,8 s.
  - 10 skip: tập tham số rỗng của `apps/api/core/tests/test_common.py:119/128/137/151` ("got empty parameter set for (operation)"), đúng ngoại lệ BE-00 §12.
  - `1 deselected` là test **`perf`** `packages/ml_contracts/tests/test_synthetic.py:225` của B5-01, **không phải `gpu`** như ghi chú giao việc. Không có test `gpu` nào (`--collect-only -m gpu`: 0). Bước 5 loại nó đúng luật (`-m "not gpu and not perf"`); bước 5b của nhánh worker chỉ chạy `perf` của đơn vị bị chạm.
- Độ phủ (in từ `tools.coverage_gate` của lượt trên, không lấy từ báo cáo tác giả):
  - tổng: dòng **99,32 %** · nhánh **97,28 %**
  - `packages/db`: dòng 98,77 % · nhánh 97,32 %
  - `packages/testing`: dòng 99,09 % · nhánh 100,00 %
  - `tools`: dòng 98,62 % · nhánh 95,20 %
  - tập file bị chạm: dòng **99,74 %** · nhánh **97,44 %**

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm `node_modules` (mới, FIX-032) | đạt: `/work/contract-node/3c583539a0314ecd` đã có trên volume nên không chạy `npm` |
| 1 | `ruff format --check` | đạt (312 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (275 file) |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt: 0 đơn vị `perf` bị chạm; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5 |
| 6 | `lint_migrations` → `migrate_check` | đạt (3 revision, 9/9) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt: H1 186 mẫu. H3/H4/H5 `không áp dụng` **hợp lệ** (B1-02, B3-05, B4-01 chưa có `changes/*.md`) |
| 8 | openapi | đạt (nhánh worker, không `--compare`) |

Cuối lượt, `contract-samples/` của worktree có đúng 186 file trong `auth_login`, `auth_logout`, `auth_refresh`. Đây là FIX-008 chạy thật.

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt: đầu phiên và cuối phiên. `.cache/rv` của probe đã xoá |
| `changes/B0-01.md`, `changes/B0-03.md` có, 3–10 dòng | đạt (8 và 8 dòng). Nhánh FIX không cần file `changes` mới |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt, cả 11 commit (dài nhất 69 ký tự, `f3559f1`) |
| Trailer đọc được (R-36b) | đạt. Mỗi commit in `Prompt:` bằng `%(trailers:key=Prompt,valueonly)` (`B0-03` cho `e3f2598`, `B0-01` cho các commit còn lại). Bảy commit FIX có thêm `Fix: FIX-006…010/032`; `caaf5ab` mang `Fix: FIX-009`. Khối trailer liền nhau, có dòng trống trước |
| Đụng `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/charter.py` | không |
| `tools/verify/*` | có (`steps.py`). Đúng chủ: B0-01 |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không. Một `# type: ignore[import-untyped]` mới có mã (`services.py:22`), cùng lối và cùng chú thích dòng 21 của năm import `testcontainers` sẵn có |
| `conftest.py` lồng, file cấu hình riêng, thư viện mới | không |

File ngoài `[4]` của spec:
- `packages/testing/fixtures/services.py` (FIX-009 bổ sung). Người điều phối đã nới phạm vi (trả lời `ask` msg_b999fd00190a) và file thuộc B0-01 (`changes/B0-01.md`).
- `packages/testing/fixtures/db.py` và `packages/db/tests/test_fixture_timings.py` (FIX-010): commit riêng `Prompt: B0-03`, đúng chủ.

Không điều kiện dừng sớm nào kích hoạt.

## Công cụ kiểm tại chỗ

Mọi probe chạy trong container verify (`bash tools/verify/run.sh shell < script.sh`, bản sao `/tmp/w`). Bản file của `main` đặt tạm ở `.cache/rv/` (git bỏ qua) rồi `cp` đè; đã xoá. Script lưu ở scratchpad của phiên (`probe0..4.sh`).

- **P0: mã nguồn `testcontainers` 4.13.3.**
  - Mỗi container dựng một `DockerClient` riêng (`core/container.py:85` `self._docker = DockerClient(...)`).
  - `get_container_host_ip` (`:226-241`) và `_get_exposed_port` (`:252-256`) đều hỏi `self.get_docker_client().get_connection_mode()`.
  - Mọi đường chờ sẵn sàng và dựng URL (`redis/__init__.py:63,94`, `minio/__init__.py:76,93`, `wait_strategies.py:349,553`) chỉ đi qua hai hàm trên.
  - Ryuk (`:355`) dùng client của chính nó.
  - Kết luận: ghi đè `get_connection_mode` trên client của từng bản ephemeral là **đủ và không lan** sang bản dùng chung, đúng docstring `_via_mapped_port`.
- **P1: đỏ/xanh của FIX-006, FIX-008, FIX-032.**
  - `steps.py` của `main` + test của nhánh → **9 failed**, 6 passed:
    - FIX-006: `test_clean_dir_không_nuốt_lỗi_xoá_mục_con` → `DID NOT RAISE PermissionError`.
    - FIX-008: `test_verify_chép_mẫu_golden_ra_thư_mục_ra` → `['cũ.json'] == ['op/C01-1.json']`; `test_verify_không_có_mẫu_thì_thư_mục_ra_rỗng`.
    - FIX-032: `test_verify_làm_ấm_node_modules_trước_bước_5[argv0..3]` (lệnh đầu là `ruff format`/`coverage run`, hoặc không có lệnh nào); `test_verify_làm_ấm_hỏng_là_lỗi_hạ_tầng_của_cổng[error0,1]`.
  - Xanh ở cả hai bản, đúng như chờ: `test_clean_dir_xoá_cả_thư_mục_con_giữ_gốc`, `test_verify_ngoài_container_không_chép`, `test_verify_không_bước_cần_runner_thì_không_làm_ấm` ×2 (chúng canh nhánh "không làm").
  - `steps.py` của nhánh: `test_steps_commands.py` **57 passed**.
- **P2: FIX-010.** `db.py` của `main` → `assert [10] == [180.0]` (1 failed); bản nhánh → 1 passed. Trần đọc thật qua sự kiện `do_connect`, không đọc lại settings.
- **P3: FIX-007.**
  - Chữ ký cũ `_select_one(url)`/`timeout=5` → `KeyError: 'connect_timeout_s'`.
  - Mặc định sai (`= 5`) → `assert 5 == 180.0`.
  - Bản nhánh → xanh. Xem Nit #2 về độ mạnh của test.
- **P4: FIX-009 lần đầu.** `verify.yml` của `main` → `test_container_verify_nối_thẳng_ip_container_dịch_vụ` đỏ (thiếu `TESTCONTAINERS_CONNECTION_MODE=bridge_ip`); bản nhánh → xanh.
- **P5: FIX-009 bổ sung. Gốc tái hiện được, không chỉ tin lời.**
  - `services.py` của `main` dưới `bridge_ip` → `test_ephemeral_dừng_xong_địa_chỉ_không_về_tay_bản_dựng_sau` **3 failed**: `('172.17.0.6', 6379) != ('172.17.0.6', 6379)`, cùng dạng với 5432 và 9000.
  - Thăm dò cơ chế trên bản cũ, 3 lượt "dựng A, dừng A, dựng B":
    - 2/3 lượt B nhận **đúng** IP của A, và `PING` tới URL của A trả `True` (bản đã dừng "vẫn sống");
    - 1/3 lượt B nhận IP khác và gặp 111.
  - Bản nhánh: 3/3 lượt `Error 101` ngay (0,00–0,01 s), cổng host mỗi lượt một khác.
  - `-k địa_chỉ_không_về_tay` 3 passed; cả `test_services.py` **14 passed ×2** (30,3 s; 35,9 s).
- **P6: địa chỉ thật trên nhánh.**
  - Bản dùng chung: `postgresql+asyncpg://…@172.17.0.7:5432` (IP bridge).
  - `ephemeral_postgres`/`minio`/`redis`: `host.docker.internal:<cổng map>`.
- **P7: chép mẫu golden hỏng.** `CONTRACT_SAMPLES_DIR=/tmp/cs VERIFY_OUT_DIR=/proc/rv python -m tools.verify.steps verify --steps 1` → ruff đạt, rồi `FileNotFoundError: [Errno 2] … '/proc/rv'`, traceback, **0 dòng bảng**, thoát 1 → finding #1.
- **P8: bước 0 hỏng thật.** `CONTRACT_NODE_DIR=/proc/rv … verify --steps 5` → bảng có hai dòng: `0 | làm ấm node_modules | hỏng | lỗi hạ tầng cổng: [Errno 2] …` và `5 | … | chưa chạy`; thoát 1. Không bước nào của pytest chạy.
- **P9: nhánh lạnh của bước 0, không mạng.**
  - Chép kho `npm-cache` (5,0 MB) sang một `CONTRACT_NODE_DIR` mới, đặt `npm_config_offline=true`.
  - `step_warm_node_modules` → `đạt /tmp/cold/3c583539a0314ecd` sau 1,26 s (`npm ci` thật, offline); lượt thứ hai 0,000 s.
  - `ensure_node_modules(node_dir_from_env())`, đúng lời gọi của `build_layout`, trả cùng đích.
  - Kết luận: bước 5/7 thấy đích đã có; khi kho đã có thì làm ấm không cần mạng.
- **P10: tải nhẹ trên hai đường nối Postgres,** 2 lượt × 2 000 lần nối TCP × 8 luồng.
  - IP bridge: 0 lỗi, lâu nhất 2,04 s (p99 1,02 s, SYN thử lại vì hàng đợi `listen`).
  - `host.docker.internal` + cổng map: 0 lỗi, lâu nhất 0,04 s.
  - Ở tải này **không tái hiện** được kẹt hay từ chối của chặng host. Tôi **không** tăng lên mức tác giả đo (16 luồng × 20 000): cùng Docker Desktop đang có hai lượt verify của phiên khác đi đúng chặng đó trên `main`, và dồn tải vào bộ chuyển tiếp cổng sẽ làm đỏ giả cổng của họ.
  - Bằng chứng gốc của FIX-009 lần đầu vì thế dựa trên số đo của tác giả ở NO-007. Số đo đó có phương pháp, số lượt, cổng và kết quả của cả hai đường, đủ để lặp lại.
  - Đường bridge không kém hơn ở mọi chỉ số chặn cổng: 0 lỗi, và trần 2 s dưới xa trần 10 s của app và 180 s của cổng.
- **P11: cây đã gộp** = nhánh + 14 file mã của `main`@`1a059d6` + `docs/contracts.toml`.
  - `pytest packages/storage packages/db tools packages/testing`: **650 passed**.
  - `lint_migrations`: đạt (4 revision). `migrate_check`: đạt, kể cả "tên CHECK khớp model".
  - `mypy`: 277 file sạch. `ruff check`, `ruff format --check`: sạch.
- **P12:** danh tính skip và deselected, ghi ở đầu phán quyết.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG-04 · R-33 | `cmd_verify` gọi `export_contract_samples()` **trước** `_print_table` và không bắt lỗi. Mọi `OSError` của `_clean_dir` hay `copytree` (thư mục ra thiếu, không ghi được, đĩa đầy) thoát khỏi `cmd_verify` thành traceback: bảng cổng (E.10) **không in**, và một lượt 8/8 đạt vẫn thoát 1 mà không nói vì sao. **Probe P7:** ruff đạt, rồi `FileNotFoundError '/proc/rv'`, 0 dòng bảng, mã 1. Trong container, mount `/src-out/contract-samples` luôn có nên hiếm gặp. Ngoài container, đây đúng là kịch bản NO-051 (CI của B0-09 đặt `CONTRACT_SAMPLES_DIR` mà thiếu `VERIFY_OUT_DIR`): người đọc thấy traceback thay cho bảng | `tools/verify/steps.py:265-269`, `:303-305` | In bảng trước, rồi chép trong `try/except OSError as exc:`. Khi hỏng: in `chép mẫu golden hỏng: {exc}` ra stderr và trả 1; hoặc thêm một dòng bảng "chép mẫu golden" có trạng thái `hỏng`. Thêm một test với `OUT_DIR` không ghi được: bảng vẫn in, mã thoát 1 |
| 2 | Nit | TEST-02 | Test chặn tái phát của FIX-007 chỉ đọc **mặc định** của `_select_one` bằng `inspect.signature`. Bỏ `connect_timeout_s=_STOPPED_TIMEOUT_S` ở lượt nối bản đã dừng (`:111`) thì test vẫn xanh. Khớp chữ `[6]` ("test hàm chọn trần") vì không có hàm chọn riêng; hành vi thật do hai test ephemeral canh | `tools/tests/test_services.py:135-141` | Chấp nhận được. Nếu muốn chặt hơn: bọc `asyncpg.connect` bằng `monkeypatch` để ghi `timeout` của từng lượt trong `test_ephemeral_postgres_dừng_xong_…`, rồi so `[GATE, 5, GATE]` |
| 3 | Nit | R-07 · MNT-04 | `_STOPPED_TIMEOUT_S = 5` nay là "trần bắt tay tới bản đã dừng", nhưng lượt nối MinIO đã dừng vẫn dùng số trần `timeout=2`: hai trần cho cùng một việc | `tools/tests/test_services.py:123` | `timeout=_STOPPED_TIMEOUT_S` |
| 4 | Nit | TEST-02 | Fixture `repo` không gỡ `CONTRACT_SAMPLES_DIR`. Từ FIX-008, test có sẵn `test_main_verify_in_bảng_và_mã_thoát` gọi `main(["verify"])` và chép mẫu golden **thật** của lượt cổng (`/tmp/contract-samples`, đã có ~186 file khi `tools/tests` chạy) vào `tmp_path`. Vô hại hôm nay, nhưng test phụ thuộc môi trường và thứ tự chạy; ba test FIX-032 mới thì tự `delenv` | `tools/tests/test_steps_commands.py:47-58`, `:249-264` | `monkeypatch.delenv("CONTRACT_SAMPLES_DIR", raising=False)` trong `repo`; bỏ các `delenv` lặp ở test mới |
| 5 | Nit | R-01 | Hai hàm đổi hành vi mà vẫn không có docstring: `cmd_verify` (tự thêm bước 0 khi có 5/7, chép mẫu kể cả khi đỏ) và ba factory `ephemeral_*` (nay đi cổng map, khác bản dùng chung). Lý do chỉ nằm ở comment dòng và docstring module/`_via_mapped_port` | `tools/verify/steps.py:260`; `packages/testing/fixtures/services.py:120-129` | Một câu docstring mỗi hàm; với `ephemeral_*`, trỏ về `_via_mapped_port` |
| 6 | Nit | — (sổ) | Cột "Commit" chưa khớp: FIX-009 chỉ ghi `3ca1463` dù `caaf5ab` cũng mang `Fix: FIX-009`; FIX-032 còn ghi tên nhánh | `docs/fixes.md:18`, `:41` | Người điều phối điền `3ca1463`, `caaf5ab` và `02f2b64` khi gộp (`--no-ff` giữ nguyên các sha này) |
| 7 | Nit | — (hiến chương) | NO-050 chỉ nêu biến `TESTCONTAINERS_CONNECTION_MODE=bridge_ip`. Bảng BE-00 §12 (8 bước) và ENV §2 cũng chưa có bước "0 làm ấm `node_modules`" và luật "ephemeral đi `host.docker.internal` + cổng map, bản dùng chung đi IP bridge" | `DEBT.md:71` (NO-050) | Người điều phối mở rộng chữ NO-050 để khi sửa hiến chương làm cả ba ý một lần |

**P0: 0 · P1: 0 · P2: 0 · P3: 1 · Nit: 6**

## Những chỗ đã soi kỹ và **đạt**

- **FIX-006 (NO-008), sửa ở gốc chung.**
  - `_clean_dir` là chỗ **mọi** việc ghi ra `/src-out` đi qua: `lock`, `openapi`, `merge-heads`, và nay cả `contract-samples`.
  - Hàm xoá từng mục con: thư mục thật dùng `rmtree` không `ignore_errors`; file và symlink dùng `unlink`, nên symlink tới thư mục không bị `rmtree` đi theo. Chính mount point được giữ (NO-001, `test_lock_thư_mục_ra_là_mount_point…` vẫn xanh).
  - Mô phỏng lỗi bằng `os.unlink` từ chối đúng một file là đúng: container chạy bằng root, nên quyền tệp không dựng được lỗi này.
  - `cmd_gc` vẫn `rmtree(..., ignore_errors=True)` cho `venv-*`/`mypy-*`: đó là việc dọn rác khác, ngoài NO-008, không phải người gọi `_clean_dir`.
- **FIX-007 (NO-042).** `_select_one` mặc định trần cổng; chỉ lượt nối bản đã dừng truyền 5 s. `test_postgres_16_lên_thật` có trần tường minh (R-24).
- **FIX-008 (NO-043).** Chép chạy sau `run_steps` kể cả khi có bước hỏng. Không đặt `CONTRACT_SAMPLES_DIR` thì không làm gì. Đặt mà chưa có mẫu thì thư mục ra được làm rỗng, không còn mẫu cũ. Probe cổng: 186 file ra đúng chỗ.
- **FIX-009 (NO-007), cả hai commit.**
  - Lần đầu: một biến môi trường trong `verify.yml`. CI chạy ngoài container không đặt biến này, nên hành vi CI không đổi (testcontainers chỉ đọc `TESTCONTAINERS_CONNECTION_MODE`).
  - Bổ sung: sửa ở **chỗ duy nhất** mọi người gọi đi qua (ba factory `ephemeral_*`), không vá từng test. `grep` người gọi trên nhánh đã gộp `main`: `apps/api/auth/tests/test_refresh.py:410`, `test_verifier.py:268`, `apps/api/core/tests/test_routing.py:248`, `packages/db/tests/test_errors.py:38`, `packages/messaging/tests/test_streams.py:262`, `packages/storage/tests/test_s3.py:93`, `packages/testing/fixtures/messaging.py:177`. Cả bảy lấy URL qua `get_container_host_ip`/`get_exposed_port`, nên đều theo đường mới (P0, P6).
  - Đường mới là đúng đường mà cả bảy đang đi trên `main` hôm nay (`main` chưa có `bridge_ip`), nên **không hồi quy**; phần lớn kết nối (bản dùng chung) thì rời khỏi chặng host.
  - Gốc "IP bridge bị cấp lại ngay" tự tái hiện được (P5): 2/3 lượt URL của bản đã dừng ping trúng container kế.
  - `_STOPPED` bỏ `113` là đúng số đo: bản đã dừng nay hỏng ngay với 101/111. Việc nhận `''`/`timed out` có lý do ghi trong docstring (chặng host kẹt).
  - Test ranh giới (`!= endpoint`) sẽ đỏ nếu bản `testcontainers` sau không còn hỏi `get_connection_mode` trên client, nên ghi đè có lưới đỡ theo R-05.
- **Phần hở tác giả ghi ở NO-007 đứng được.** Kẹt ~69 s của chặng host chỉ còn chạm lượt nối **trước** khi dừng của bảy chỗ trên, mỗi chỗ vài kết nối. Tác giả đo 6 lần kẹt trên 200 000 lần nối ở tải nặng. Mọi kết nối trên `main` hiện nay đều đi chặng đó, nên nhánh giảm hẳn mức phơi. Ghi trong dòng `✅` có số đo và đường chữa (mạng riêng hay service trong `verify.yml`) là trung thực.
- **FIX-010 (NO-036).** `db_sessionmaker` mang `int(GATE_CONNECT_TIMEOUT_S)`, cùng cách `api_env` của B0-06 và `test_jobs.py:105` của B1-01. Một số test B0-03 khác vẫn dựng `DatabaseSettings(database_url=db_url)` 10 s (`test_engine.py:46`, `test_hooks.py:205/222/294`). Chúng nối **bản dùng chung**, mà bản này nay đi IP bridge (FIX-009), nên lớp lỗi của NO-036 không còn chạm chúng; không nêu finding.
- **FIX-032 (NO-048).**
  - Đúng `[5]`: gọi `ensure_node_modules(node_dir_from_env())` như `build_layout`, không truyền `cache_dir`/`package_dir`. Bộ thay trong test cố ý chỉ nhận một đối số vị trí, nên lệch lời gọi là `TypeError`.
  - Chỉ chạy khi `--steps` rỗng hay có 5/7. Lỗi `RunnerError`/`OSError` thành "lỗi hạ tầng cổng", mọi bước sau "chưa chạy" (P8).
  - Nhánh lạnh chạy được offline từ kho (P9). Kho `<node_dir>/npm-cache` mà bước 0 làm đầy cũng là kho `test_runner_client.py:21` dùng, nên test cài thật của B0-07 ở bước 5 cũng không ra mạng.
  - Hai lượt verify lạnh song song vẫn an toàn nhờ `publish` đổi tên nguyên tử (B0-07).
  - `step_warm_node_modules` có docstring đủ lý do. Lời gọi tới `tools.contract` qua `lint-imports` đạt.
- **Hợp nhất với `main`.**
  - Các API nhánh đổi: `_start_redis` bị bỏ, `_redis` mới, `_via_mapped_port`, `_clean_dir`, `_select_one`, `_STOPPED`, `export_contract_samples`. `grep` trên cả cây nhánh và 14 file mã mới của `main`@`1a059d6`: ngoài các file của nhánh, không ai gọi chúng, chỉ bảy người gọi `ephemeral_*` ở trên.
  - `packages/storage/tests/fault_proxy.py` mới của `main` dùng `minio_endpoint` dùng chung (nay là IP bridge) qua proxy trong tiến trình, và xanh ở P11.
- **Kích thước.** ≈ 90 dòng mã sản phẩm, ≈ 230 dòng test: dưới trần 400 của MNT-05.

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | Gộp `main` hai lần (`900494a`, `22c259b`), không rebase | **Đứng được.** Đúng giao việc FIX-032..037 ("gộp `main` vào, không rebase — giữ sha"). Xung đột `DEBT.md` được giải giữ cả hai phía: không mất dòng nào so với `7ba37ae` (diff chỉ đổi 6 dòng, thêm 2) |
| 2 | Bước làm ấm đứng ở "0", trước bước 1, chứ không ngay trước bước 5 | **Đứng được.** `[5]` ghi "pha chuẩn bị, **trước** bước 5". Hỏng hạ tầng thì dừng sớm là đúng luật "chưa chạy" của E.10. Cái giá là npm hỏng thì lint không chạy, nhưng hiếm vì volume ấm |
| 3 | Nhánh lạnh (`npm ci` thật) chưa chạy trong cổng | **Đứng được, đã tự kiểm** (P9: `npm ci` offline từ kho qua đúng bước 0). Nhánh "npm hỏng thật" thì `test_runner_client.py` đã có test |
| 4 | Sửa `packages/testing/fixtures/services.py` ngoài `[4]` ban đầu | **Đứng được.** Người điều phối nới phạm vi (msg_b999fd00190a); file thuộc B0-01 |
| — | Phán quyết của người điều phối trong lúc làm (FIX-009 bổ sung: ephemeral đi cổng map, bản dùng chung giữ IP bridge) | **Đúng gốc** (P0, P5), **đỏ trước thật** (3 failed), phần hở còn lại ghi trung thực ở NO-007 (xem mục trên) |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Dòng các nợ nhánh đóng nói đúng sự thật | đạt: NO-007 (P0, P4–P6, P10), NO-008 (P1), NO-036 (P2), NO-042 (P3), NO-043 (P1 + 186 file ra thật), NO-048 (P1, P8, P9). Mỗi dòng `✅` có ngày đóng, mã FIX, tên test, lượt đỏ → xanh; đóng trong chính commit sửa. Số đếm tác giả ghi khớp số tôi đo ("đỏ 6 failed" của FIX-032; "3 failed `('172.17.0.5', 6379) != …`" cùng dạng với `172.17.0.6` của tôi) |
| Nợ tác giả nêu đều có dòng | đạt: NO-050 (hiến chương, người điều phối) và NO-051 (ràng buộc bàn giao cho CI của B0-09) để `⬜`, đúng đoạn "Không có FIX" của `docs/fixes.md` |
| Nợ P0/P1 còn `⬜`/`🔧` do nhánh để lại | không |
| Nợ do review này chỉ ra đã có dòng | **chưa**, xem dưới |

Dòng đề xuất (người điều phối cấp id; phiên này **không** tự ghi `DEBT.md`), nếu finding #1 không được sửa trong nhánh:

- `| ⬜ | NO-<nnn> | 2026-09-22 | | cmd_verify chép mẫu golden (export_contract_samples) trước khi in bảng và không bắt lỗi: thư mục ra thiếu hay không ghi được → traceback, không có bảng cổng, lượt 8/8 đạt vẫn thoát 1 | FIX-008 đặt lời gọi trước _print_table; OSError của _clean_dir/copytree nổi thẳng ra khỏi cmd_verify | B0-01 (tools/verify/steps.py:265-269) | P3 | mở — review merge 2026-09-22 finding #1 (probe: VERIFY_OUT_DIR=/proc/rv → FileNotFoundError, 0 dòng bảng). Chữa: in bảng trước, bọc chép mẫu trong try/except OSError → in lỗi ra stderr và thoát 1 (hay thêm dòng bảng "chép mẫu golden"), kèm test OUT_DIR không ghi được |`

Nit #2–#7 do tác giả và người điều phối tự quyết, không cần dòng nợ. Riêng Nit #7 là đề nghị mở rộng chữ của NO-050 đang mở.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 (P3 #1) | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit #2, #4) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 (Nit #7) | 0,25 |
| MNT – Bảo trì | 3 % | 5 (Nit #3, #5, #6) | 0,15 |

Tổng: 1,25 + 0,75 + 0,60 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,15 = **4,85 / 5**

## PHÁN QUYẾT: APPROVE

**Vì sao duyệt:**
- Cổng thoát 0 trên lượt tôi tự chạy: `1982 passed`; 10 skip đúng ngoại lệ; `1 deselected` là test `perf` hợp lệ.
- Độ phủ đạt ở mọi gói bị chạm (`tools` 98,62 % / 95,20 %; tập file bị chạm 99,74 % / 97,44 %).
- Không có P0/P1/P2. Điểm 4,85 ≥ 4,0.

**Sáu FIX đều đúng gốc và đỏ trước thật (tự tái hiện, không chỉ tin báo cáo):**
- `_clean_dir` sửa ở chỗ mọi việc ghi ra đi qua.
- Trần bắt tay cổng cho `db_sessionmaker` và `test_services`.
- Chép mẫu golden cuối lượt, kể cả khi đỏ.
- Bước 0 làm ấm gọi đúng lời gọi của `build_layout`; tự kiểm cả nhánh lạnh offline lẫn nhánh hỏng thật.
- FIX-009 hai tầng: bản dùng chung rời chặng `host.docker.internal`. Bản ephemeral quay về cổng map sau khi gốc "IP bridge bị cấp lại ngay" được chứng minh: 2/3 lượt URL của bản đã dừng ping trúng container khác trên bản cũ, 3/3 hỏng ngay trên bản mới. Sửa ở ba factory mà cả bảy người gọi đi qua.

**Mọi dòng `DEBT.md` nhánh đóng nói đúng sự thật.** Phần hở còn lại của NO-007 được ghi trung thực và đứng được.

**Finding còn lại** là một P3 về thứ tự "chép mẫu rồi mới in bảng" (#1) và sáu Nit; không cái nào chặn merge.

Điều kiện cho phiên merge:

1. **`main` đã đi tiếp tới `1a059d6`** sau lần gộp cuối của tác giả. `git merge-tree --write-tree main 22c259b`: xung đột **chỉ** ở `DEBT.md`; `docs/fixes.md` tự gộp.
   - Giải bằng cách giữ cả hai phía:
     - của `main`: `✅` NO-009..017, `✅` NO-057/058, các dòng mới NO-068..073;
     - của nhánh: `✅` NO-007/008/036/042/043/048 và `⬜` NO-050/051.
   - Mã của cây đã gộp xanh ở probe P11 (650 test của bốn gói liên quan, bước 6 đạt). Sau merge vẫn phải chạy `verify` tích hợp trên `main` như thường lệ (xuất `openapi.json` ra gốc trước bước 8).
2. Gộp bằng `git merge --no-ff` (R-36): nhánh mang trailer của B0-01 **và** B0-03, cùng `Fix: FIX-006…010/032`. **Không** squash; giữ các sha đã ghi ở `docs/fixes.md`.
3. Điền cột "Commit" của `docs/fixes.md`: FIX-009 → `3ca1463`, `caaf5ab`; FIX-032 → `02f2b64` (Nit #6).
4. Trước khi merge, nếu không sửa #1 trong nhánh: ghi dòng `⬜` P3 đề xuất ở trên (R-38). Sau merge: sửa hiến chương theo NO-050, mở rộng như Nit #7.
