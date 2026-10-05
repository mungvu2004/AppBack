# Review merge fix/debt-02-tich-hop → main (DEBT-02 đợt W3–W10, lượt 2 — chỉ vòng sửa)

- Ngày: 2026-10-05 · Reviewer: phiên /merge-review độc lập (R-37) · Commit đầu nhánh: `5ee5031ccddc`
- Phạm vi lượt 2: vòng sửa F1–F24 của lượt 1 (`2026-10-05-fix-debt-02-tich-hop.md`). Lịch sử viết lại bằng filter-branch (F1):
  `b017a58` → `f330ed4` (cây giống hệt `249e601`). Diff vòng sửa `git diff f330ed4 5ee5031`: 49 tệp, +855/−174 = nhánh RA
  `fix/debt-02-r1-deploy-tools`, RB `fix/debt-02-r1-ml-worker`, RC `fix/debt-02-r1-api` + commit MF (`docs(contract)`, `docs(debt)`,
  `docs(fixes)`, `docs(security)`). Cây làm việc sạch; `changes/DEBT-02.md` có.
- Cổng: phạm vi **đầy đủ**. Vòng sửa chạm `tools/case_gate.py`, `tools/coverage_gate.py`, `deploy/backup` và cần bước 8 integration,
  nên theo R-33b phải chạy đủ. Reviewer không chạy, MF chạy: `bash tools/verify/run.sh verify` trên `5ee5031`, **mã thoát 0**
  (`backend/dieu-phoi/chay/DEBT-02/R/gate-r1.log`). Bước 8 có `VERIFY_BRANCH=integration`
  (`--compare docs/contracts/openapi.json`) cũng **mã thoát 0** (`R/mf-step8-2.log`, log `…-5ee5031ccddc.log`).
- Độ phủ (gate-r1.log): tổng dòng 99,48 % · nhánh 98,02 %; `coverage_gate: đạt` (mọi đơn vị bị chạm ≥ 90/90).
- Đỏ/xanh tự tái hiện: 8 test của vòng sửa (RA 4, RB 3, RC 1), chạy trong một container `run.sh shell`. Mỗi test **xanh** trên
  `5ee5031` rồi **đỏ** khi đảo tệp nguồn về `f330ed4`, riêng RC-F14 đỏ bằng đột biến bỏ guard (`R/rg-r2.sh`, `R/rg-r2.log`).

## Bảng E.10 (mã thoát thật, gate-r1.log @ 5ee5031)

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | ruff format --check | đạt |
| 2 | ruff check | đạt |
| 3 | mypy --strict | đạt |
| 4 | lint-imports | đạt |
| 5 | pytest -n (cov) → coverage_gate | đạt (8 409 passed) |
| 5b | pytest -m perf → case_gate | đạt (39 passed) |
| 6 | lint_migrations → migrate_check | đạt |
| 7 | H1 H3 H4 H5 | đạt |
| 8 | openapi | đạt (`VERIFY_BRANCH=integration`, so bản tham chiếu — mf-step8-2.log) |

Tổng: mã thoát 0.

## Đỏ (nguồn f330ed4) → xanh (5ee5031)

| Cụm | Test | Đảo | Đỏ do |
|---|---|---|---|
| RA F4 | `test_backup.py -k any_env_without_age_recipient` (3 ca) | `deploy/backup/backup.sh` | staging/dev/`APP_ENV` rỗng vẫn chạy pg_dump, rc 0 |
| RA F7 | `test_case_gate.py::test_parse_junit_skipped_xfail` | `tools/case_gate.py` | `other.xfail` bị tính là xfail |
| RA F19 | `test_logging.py::test_mask_url_userinfo_password` | `packages/core/logging.py` | `redis://:***@b` (host bị che) |
| RA F24 | `test_coverage_gate.py -k không_câu_lệnh` | `tools/coverage_gate.py` | in `deploy: 100.00%` giả |
| RB F8 | `test_sandbox.py::test_ml_eval_sandbox_result_without_metrics` (5 ca mới) | `apps/ml/ml_eval/tasks.py` | `AttributeError` thô với `null`/`[]`/`5`, `ValueError` với `"x"` |
| RB F9 | `test_sandbox.py -k unterminated_previous_line` | `apps/ml/ml_eval/sandbox.py` | dòng kết quả dính dòng lạ → `MODEL_FORMAT_UNSUPPORTED` |
| RB F17 | `test_tasks.py -k child_env_is_allowlisted` | `apps/ml/training_runner/tasks.py` | `KeyError: 'LOG_LEVEL'` |
| RC F14 | `test_notify.py -k row_trimmed_between_insert_and_select` | đột biến `service.py:157` bỏ `existing is not None` | `AttributeError: 'NoneType'…stream_id` |

## Soát bắt buộc

- **F1 — đứng.** Lệnh `git log --no-merges --format='%h %(trailers:key=Prompt,valueonly,separator=)' main..5ee5031 | awk 'NF<2'` ra
  rỗng: cả 290 commit đều có trailer git đọc được. 14 commit viết lại (`R/f1-map.txt`) mang `Prompt`/`Fix` đúng bảng F1 lượt 1:
  B0-01/FIX-350, B0-02/FIX-344, B6-03b/FIX-345, B0-10/FIX-339 và FIX-341, B0-08/FIX-340, B6-02b/FIX-343, B7-02/FIX-338 và FIX-311;
  docs DEBT-02 giữ `DEBT-02`. Đỉnh trước/sau filter-branch (`fbb4f1a`/`d70e844`) cùng cây `00d0b6c`; chuỗi `%T %s` của cả 332 commit
  `main..` giống hệt. K27 của 34 commit vòng sửa: mỗi commit chỉ chạm tệp của một chủ (`tao_so_tra.py --chu`) và `Prompt` khớp chủ đó.
- **F2 — đứng.** Không xoá test đúng của B0-03 (tệp không có trên `main`, nên hoàn lại = xoá). Việc tệp nằm trong commit có
  `Prompt: B1-01` được ghi rõ là K27 lịch sử ở khối FIX-304 [4]. Câu "F1 xử lý" trong `R/RC/tai-hien-F2.md` sai: F1 không viết lại
  `12e0178`/`13a4e2c`. Tệp đó nằm ngoài repo nên không thành finding.
- **F3 — đứng.** `docs/contracts/openapi.json` đã làm mới (`76db7b2`). Bước 8 integration so bản tham chiếu đạt.
  `changes/DEBT-02.md:10` liệt kê đủ ba thay đổi cộng thêm (NO-236, NO-237, NO-253).
- **F4 — đứng.** Câu ở `BE-00.md:450` (`56cfdd6`, chỉ chạm tài liệu, có `Charter-Approved: …/duyet-nguoi-dung-2026-10-05.md`) khớp
  từng chữ với câu C1 trong tệp duyệt và `W8/C32/no335-nhap.md`. `backup.sh:90` thoát 1 khi thiếu recipient, trừ khi
  `BACKUP_ALLOW_PLAINTEXT` đúng bằng `1`; production vẫn thoát 1 kể cả có cờ (`test_backup__production_ignores_plaintext_opt_out`).
  `env.example:105-107` khai hai biến, cờ để rỗng. `drill.sh` chỉ đặt cờ khi máy thiếu `age`.
- **F5 — đứng.** Ba test chức năng đã bỏ `perf` và chạy ở bước 5, không còn khẳng định thời gian. Ba test `perf` mỏng dùng chung helper.
  Trần so với số đo (`R/RB/tai-hien-F5.md`): sweep 4,0 s / 1,075 s = 3,7×; quality 4,0 s / 1,017 s = 3,9×; cancel 10 s / 0,017 s.
  Bước 5b: 39 perf.
- **F6a — đứng.** FIX-273 [5] ghi lý do, và tôi đã kiểm mã: CHECK cũ (`admin_ml_datasets.py:92`) còn chặn định dạng
  `failure_code ~ FAILURE_CODE_PATTERN`, CHECK mới chỉ chặn có/không. Drop CHECK cũ sẽ mất ràng buộc định dạng.
- **F6b — đứng.** `pipeline_quality/tests` không còn chạm `_STORAGE`/`_storage` (dùng `override_quality_storage`, `open_storage`).
  `pipeline_orchestrate`/`pipeline_persist` vẫn còn `tasks._STORAGE.override`, nhưng đã có trên `main` và ngoài NO-304: không mở lại.
- **F7–F24 — đã sửa trong diff:** F7 hoàn `== "pytest.xfail"` (+ ca âm), F8, F9, F10 (`code is INTERNAL`, `retry_after is None`),
  F11, F12 (assert cấu trúc `map`), F13 (assert hành vi), F14, F15 (`MARK_MAX_DEFAULT`), F16 (`count_sql`, regex FROM|JOIN), F17,
  F18, F19, F20 (tsv NO-196, giờ duyệt 01:16Z, phạm vi H4-B trong tệp duyệt), F21 (đổi tên), F22, F23 (revision về đúng bản `main`,
  `git diff main` rỗng), F24. [11].3 trên diff vòng sửa: chỉ còn các dòng `xfail` của F7 (đúng ý) và một `type: ignore[import-untyped]`
  có lý do.

## Finding

| # | Mức | ID | Mô tả + bằng chứng | Vị trí | Đề xuất sửa | Chủ |
|---|---|---|---|---|---|---|
| G1 | P3 | R-36, sổ FIX (docs) | `docs/fixes.md` trỏ tới commit **không nằm trên nhánh**. Gộp vào `main` thì [7] NGHIỆM THU của các khối này trỏ vào sha mồ côi. Ba nhóm: (a) FIX-351…371 dẫn sha nhánh worker **trước khi gộp**, khoảng 24 sha: `19e6dd5`→`817c9eb`, `21a1a1d`→`781eab5`, `2d1184d`→`56cfdd6`, `6aecb51`→`d9c63cc`, `9960254`→`8b2cf5f`, `a51986a`→`6cb36c4`, `debb053`→`6af79a4`, `39cec55`→`5b802de`, `031f3a7`→`74c4d29`, `3ada64f`→`6bcc063`, `9e5c81b`→`a536dfe`, `6b2569a`/`9612c27`/`2a54c11`→`1069c82`/`767ce40`/`caefa93`, `8928b9d`→`9ee197f`, `a3a6113`→`62f2595`, `27e4a49`→`9fa8880`, `8a1a8be`→`d25111d`, `c72b5e3`→`f0b5e17`, `d9ab535`→`64eaabb`, `ff02ba7`→`427a5de`, `a518dd4`→`990e086`, `a5bdb63`→`04a0aef`, `f1d735c`→`0feaea6`, `91e8ae7`→`a477e4f`, `f2e817e`→`1973195`, `ee6a42f`→`f2026ba`, `2a68539`→`8041fa1`. (b) Commit `c17f338` "repoint shas rewritten by the trailer fix" bỏ sót 4 sha có ngay trong `MF/sha-remap.txt`: `f6d0f68`→`97ab36a`, `f5eb942`→`c4db805`, `ffb507d`→`e1f3a78`, `bab36ff`→`53db9fc` (FIX-314/315/316). (c) Sót từ trước F1: `55ec55b`→`049c0bc`, `c6ec3af`→`fd2d828` (FIX-311/314/316), `10364ed`→`dfba078` (FIX-313), `70eaccf`→`cfb8a9b` (FIX-312). Lệnh kiểm: mọi sha trong dòng `+` của `git diff main 5ee5031 -- docs/fixes.md` phải `merge-base --is-ancestor … 5ee5031` | `docs/fixes.md:277-282,315,2983,3013,3023,3033,3363` và các khối FIX-351…371 | Commit `docs(fixes)` thay theo bảng trên (khớp tiêu đề commit trong `main..5ee5031`), rồi chạy lại lệnh kiểm: ra rỗng với mọi khối FIX-175…371 | DEBT-02 (điều phối) |
| G2 | Nit | SEC-xx (nhất quán) | Ca "opt-out chạy được" dùng `APP_ENV=staging`, trong khi C1 ghi "chỉ dev, diễn tập" và `env.example:106` ghi "KHÔNG đặt ở staging/production". Test vì thế khẳng định staging được ghi bản rõ. Mã đúng câu duyệt (cờ tường minh), nhưng test nói ngược tài liệu | `deploy/backup/tests/test_backup.py:209-211` | Đổi `APP_ENV` của ca này thành `dev` (hoặc rỗng) | B0-10 |
| G3 | Nit | [6] E, F7 nửa sau | Lượt 1 F7 đề xuất ghi `tools/case_gate.py:262` và `tools/tests/test_case_gate.py` (dòng `pytest.xfail`) vào danh sách dương tính giả của audit. `R/mf-audit-r1.log` vẫn báo `HỎNG skip/xfail (K24)` hai dòng đó, cùng `HỎNG ngoài so_huu: .github/workflows/notify.yml` (`7fec0e1`, `Prompt: B0-10`), nhưng chưa có bản ghi dương tính giả cho lượt này (`MF/buoc4.md` chỉ có lượt 0) | `backend/dieu-phoi/chay/DEBT-02/MF/` | Thêm mục lượt r1 vào `MF/buoc4.md`: ba dòng, mỗi dòng một lý do | DEBT-02 (điều phối) |

Không có P0/P1/P2. Theo `backend/prompts/DEBT-02.md:102-103`, G1–G3 phải sửa trước khi gộp, không ghi nợ. Cả ba chỉ đụng tài liệu và test
(G2 là một chuỗi env trong test), nên **không cần review lượt 3**. G2 chạm test nên sau khi sửa phải chạy
`run.sh verify --steps 1,2` + `pytest deploy/backup/tests/test_backup.py` (R-33b đích).

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 4,5 (G2 Nit) | 1,125 |
| CON – Đồng thời & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & hợp đồng | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS – Vận hành / quy trình | 5 % | 3 (G1 P3, G3 Nit) | 0,15 |
| MNT – Bảo trì | 3 % | 5 | 0,15 |

Tổng: **4,78 / 5**

## PHÁN QUYẾT: APPROVE

Vòng sửa đóng đủ F1–F24 của lượt 1, có bằng chứng tự kiểm:
- trailer git đọc được ở cả 290 commit, đúng chủ, cây trước/sau filter-branch giống hệt;
- openapi khớp bản tham chiếu ở bước 8 integration;
- `backup.sh` và hiến chương đúng câu C1 đã duyệt, production chặn cả cờ opt-out;
- test chức năng đã về bước 5, trần perf ≥ 3× số đo;
- cổng đầy đủ thoát 0;
- 8 test mới đỏ→xanh.

Không có P0/P1/P2. Trước khi gộp, điều phối sửa trên nhánh (chỉ tài liệu/test, không cần lượt 3):
1. G1: repoint sha trong `docs/fixes.md` theo bảng, lệnh kiểm ra rỗng.
2. G2: đổi `APP_ENV` của ca opt-out sang `dev`, rồi chạy cổng đích như trên.
3. G3: ghi ba dòng dương tính giả của `mf-audit-r1.log`.
