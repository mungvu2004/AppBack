# Review merge fix/debt-02-tich-hop → main (DEBT-02 đợt W3–W10, lượt 1)

- Ngày: 2026-10-05 · Reviewer: phiên /merge-review độc lập (R-37) · Commit đầu nhánh: `b017a5830735`
- Phạm vi: `git diff main...b017a58` — 371 tệp, +9 596/−2 182, 297 commit (256 không phải merge, 41 merge); base `dcc9153`,
  `main` đã thêm 2 commit chỉ `DEBT.md` (`cad793c`, `e5ff8e6`). Cây làm việc sạch; `changes/DEBT-02.md` có.
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 1, lượt 1) — **không chạy lại**, đọc `backend/dieu-phoi/chay/DEBT-02/MF/gate-1.log`:
  `bash tools/verify/run.sh verify` trên `99646c4`, **mã thoát 0**. `git diff --stat 99646c4 b017a58` = chỉ `docs/fixes.md`
  (+1 386), không mã → kết quả cổng áp được cho `b017a58`. Nhánh chạy với `VERIFY_BRANCH=worker` nên bước 8 **chỉ xuất**
  openapi, không so bản tham chiếu (xem F3).
- Độ phủ (gate-1.log): tổng dòng 99,47 % · nhánh 98,00 %; mọi đơn vị bị chạm ≥ 90/90 (`coverage_gate: đạt`).
- Đỏ/xanh tự tái hiện: 23 test chặn tái phát, mỗi test **xanh trên nhánh** rồi **đỏ** khi đảo tệp nguồn của FIX về bản
  `main` (`run.sh shell`, 3 container lần lượt; log `backend/dieu-phoi/chay/DEBT-02/R/rg-b{1,2,3}.log`).

## Bảng E.10 (mã thoát thật, gate-1.log @ 99646c4)

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | ruff format --check | đạt |
| 2 | ruff check | đạt |
| 3 | mypy --strict | đạt |
| 4 | lint-imports | đạt |
| 5 | pytest -n 6 (cov) → coverage_gate | đạt (8 385 passed) |
| 5b | pytest -m perf → case_gate | đạt (40 passed) |
| 6 | lint_migrations → migrate_check | đạt (23 revision, 1 head) |
| 7 | H1 H3 H4 H5 (AppFront `9cf0b0bf`) | đạt |
| 8 | openapi | đạt (chỉ xuất — nhánh `worker`) |

Tổng: mã thoát 0.

## Đỏ trên main → xanh trên nhánh (tự chạy)

| Đợt | Test | Đảo về main | Đỏ do |
|---|---|---|---|
| W3 | `test_classic.py::…four_evenly_spaced_strokes_between_walls_are_not_wall` | `walls/classic.py` | `array_equal` False (NO-348) |
| W3 | `test_vectorize.py::…very_thin_wall_on_very_thick_wall_is_kept` | `walls/vectorize.py` | "mất vách ngắn" (NO-288) |
| W3 | `test_trainer_units.py::test_on_fit_epoch_end__nan_loss_keeps_the_valid_map50` | `training_yolo/trainer.py` | `None == 0.4` (NO-320) |
| W4 | `test_post_rules.py::…duplicate_wall_id_human_copy_untouched` | `rules_ai/post_rules.py` | tường người bị đổi (NO-251) |
| W4 | `test_settings.py::test_secret_key_placeholder_rejected_outside_dev` | `core/settings.py` | DID NOT RAISE (NO-328) |
| W4 | `test_logging.py::test_mask_url_userinfo_password` | `core/logging.py` | mật khẩu chứa `@` lộ (NO-329) |
| W4 | `test_writer.py::test_write_log__one_statement_per_chunk` | `spatial_write/writer.py` | executemany (NO-296) |
| W5 | `test_redis.py::test_streams_clients__retry_only_connection_failures` | `messaging/redis.py` | `redis.TimeoutError` còn trong retry (NO-187) |
| W5 | `test_minio_init.py::…revoke_fails_when_mc_entities_fails__no199` | `minio/init.sh` | `init.sh` thoát 0 (NO-199) |
| W6 | `test_units.py::test_body__range_is_checked_on_the_raw_number_not_the_rounded_one` | `project_settings/schemas.py` | DID NOT RAISE (NO-214) |
| W6 | `test_memberships.py::…empty_batch_runs_no_query` | `projects/memberships.py` | 1 query ≠ 0 (NO-193) |
| W7 | `test_routes_mark.py::…openapi_keeps_bounds` | `notifications/schemas.py` | `KeyError: minItems` (NO-253) |
| W7 | `test_migrate_check.py::…merge_revision_from_template_passes` | mako + `migrate_check.py` | `KeyError` tuple down_revision (NO-249) |
| W9 | `test_service.py::test_forbid_self_reports_last_admin_first` | `users/service.py` | `USER_SELF_MODIFICATION` (NO-206) |
| W9 | `test_tokens.py::test_latest_invitations__excludes_failed` | `auth_recovery/tokens.py` | lời mời hỏng còn trong kết quả (NO-150) |
| W9 | `test_routing.py::test_path_body_guard__every_real_write_with_path_params` | `core/routing.py` | 5 route thiếu guard W21 (NO-351) |
| W8 | `test_case_gate.py::test_fixed_extra_khớp_case_md` | `tools/case_gate.py` | thiếu `N14: {C11}` (NO-335) |
| W8 | `test_boundary_constants.py::test_cli_blocked__equals_importlinter_contract` | `.importlinter` | `KeyError: api-cli-no-web` (NO-352) |
| W8 | `test_nginx.py::test_nginx_streams_location_limits_conn_per_ip` | 4 tệp nginx (`streams_conn_zone.conf` mới) | thiếu `limit_conn_zone` (NO-335 H4-B) |
| W10 | `test_backup.py::test_backup__production_without_age_recipient_exits_1_before_dump` | `deploy/backup/backup.sh` | pg_dump vẫn chạy (FIX-339) |
| W10 | `test_logging.py::test_mask_key_value_in_free_text` | `core/logging.py` | `S3_SECRET_KEY=abc` lộ (FIX-344) |
| W10 | `test_drill.py::test_drill_snapshot_lists_every_table_and_object__w10` | `deploy/scripts/drill.sh` | chỉ còn `alpha` (FIX-341) |
| W10 | `test_dockerfiles.py::test_dockerfile_copied_code_is_import_closed[ml]` | `ml.Dockerfile` | thiếu COPY `packages/observability` (FIX-340) |

## Finding

Chủ = `tao_so_tra.py --chu` của tệp hỏng. Mọi finding (kể cả Nit) sửa trong vòng sửa, không ghi nợ ([6] D.3).

| # | Mức | ID | Mô tả + bằng chứng | Vị trí | Đề xuất sửa | Chủ |
|---|---|---|---|---|---|---|
| F1 | **P1** | BE-00 §13.2, R-36, SKILL §2 | 14 commit có dòng `Prompt:`/`Fix:` nhưng git **không nhận là trailer** (đoạn `Prompt/Fix` bị dòng trống tách khỏi `Co-Authored-By`): `git log --format='%(trailers:key=Prompt,valueonly)'` rỗng ở `b017a58 99646c4 6abd5bc 4870259 a681354 cf542eb e2a9bb9 5f7624d bdff809 5bb71c8 554bbca 486cd80 8aaf38f d4ec769`; trên `main` 300/300 commit gần nhất đều nhận được. Thêm: 11 commit W10 ghi `Prompt: DEBT-02`/`DEBT-02-W10-C48` trên tệp của B0-01 (`tools/verify/steps.py`), B0-02 (`packages/core/logging.py`), B0-08 (`deploy/docker/ml.Dockerfile`), B0-10 (`backup.sh`, `drill.sh`), B6-03b, B6-02b, B7-02 — [2] đòi `Prompt: <mã chủ>`; gộp `--no-ff` giữ nguyên nên tra "chủ FIX = trailer commit gần nhất" (00-SO-TRA §6.7) sẽ trỏ sai/rỗng | `R/k27.log` | Viết lại thông điệp 14 commit trên nhánh cụm/tích hợp (vd `git filter-branch --msg-filter` hay dựng lại cụm W10 rồi gộp lại): một khối trailer liền `Prompt: <chủ>` + `Fix: FIX-nnn` + `Co-Authored-By`; `Prompt` = B0-01 (FIX-350), B0-02 (FIX-344), B6-03b (FIX-345), B0-10 (FIX-339, FIX-341), B0-08 (FIX-340), B6-02b (FIX-343), B7-02 (FIX-338, FIX-311); `docs(...)` của DEBT-02 giữ `Prompt: DEBT-02`. Kiểm lại bằng `%(trailers)` = 256/256 | DEBT-02 (điều phối) |
| F2 | P2 | K27 | `12e0178` + `13a4e2c` (FIX-304, `Prompt: B1-01`) sửa `apps/api/auth/sessions.py`, `packages/db/models/auth.py` (B1-01) **và** `packages/db/tests/test_roles_mirror.py` (B0-03) trong cùng commit | `packages/db/tests/test_roles_mirror.py` | Tách test thành commit `Prompt: B0-03` (hoặc dời test vào `apps/api/auth/tests/`, thuộc B1-01) | B1-01 / B0-03 |
| F3 | P2 | API-xx, BE-00 §12 bước 8 | openapi sinh ra ≠ `docs/contracts/openapi.json` (tự xuất trong container: `cmp` thoát 1, 225 dòng khác sau chuẩn hoá): `apps__api__{floors,projects}__schemas__FloorName` → `FloorName`/`FloorDraftName`, `ids` thêm `minItems/maxItems/maxLength`, 15 op khai `project_id` (NO-236, NO-237, NO-253). Bản tham chiếu không đổi trên nhánh → bước 8 trên `main` (integration, so chuỗi) sẽ **đỏ**. `changes/DEBT-02.md:9` lại ghi "Hợp đồng FE–BE không đổi (bước 8 chỉ chạy lại)". AppFront `src` không dùng tên component nào bị đổi (grep rỗng) → không vỡ FE | `docs/contracts/openapi.json`; `changes/DEBT-02.md:9` | Trên nhánh tích hợp: `run.sh openapi` → chép `docs/contracts/openapi.json` → `verify --steps 8` với `VERIFY_BRANCH=integration` → commit `docs(contract)`; sửa dòng 9 `changes/DEBT-02.md` liệt kê ba thay đổi openapi cộng thêm | DEBT-02 (điều phối) |
| F4 | P2 | SEC-xx, [6] F (câu chữ hiến chương = bản duyệt) | `docs/charter/BE-00.md:450` (commit `dfba078`, `29c6194`) ghi "Mã hoá `age` bắt buộc **ở production** … dev/staging mã hoá khi có recipient", trong khi bản nháp người dùng duyệt (`W8/C32/no335-nhap.md` hàng C1) là "bắt buộc: thiếu `BACKUP_AGE_RECIPIENT` → thoát 1 trước khi ghi gì, trừ khi `BACKUP_ALLOW_PLAINTEXT=1` (chỉ dev, diễn tập); hai biến khai trong `env.example`". `duyet-nguoi-dung-2026-10-05.md` không duyệt thay đổi này. Mã `deploy/backup/backup.sh:87-90` theo câu đã commit (không có `BACKUP_ALLOW_PLAINTEXT`) → staging được ghi bản rõ; guard chỉ chạy khi `APP_ENV` có trong env tiến trình — chạy tay `bash backup.sh` trên VPS không nạp env → `APP_ENV` rỗng → bản rõ, rc 0 | `docs/charter/BE-00.md:450`; `deploy/backup/backup.sh:87-90` | Làm đúng bản duyệt: `backup.sh` từ chối khi thiếu recipient ở mọi env trừ `BACKUP_ALLOW_PLAINTEXT=1`, khai hai biến trong `env.example`, test cho staging + `APP_ENV` rỗng; câu hiến chương chép lại đúng bản nháp. (Hoặc người dùng duyệt tường minh câu hiện tại — ghi vào tệp duyệt.) | B0-10 + điều phối (hiến chương) |
| F5 | P2 | TEST-xx, [6] E (trần ≥ 3× số đo) | C34 / NO-343 (FIX-189/190/192) gắn `@pytest.mark.perf` lên **test chức năng** — chúng rời bước 5 (`addopts -m "not gpu and not perf"`), chỉ chạy ở 5b: `apps/worker/pipeline_steps/tests/test_sweep_rules.py:246` (assert `broker.calls == 2`, `checked_out == 0`), `apps/worker/pipeline_quality/tests/test_runtime.py:293`, `apps/ml/training_runner/tests/test_runtime.py:261`; trần `HANG_BUDGET_S = 2.0` (`test_sweep_rules.py:284`) với số đo 1,038 s = 1,9×, `test_runtime.py:329` `elapsed <= 2.0` với 1,009 s | ba tệp bên | Tách như C09: test chức năng ở bước 5 (bỏ assert thời gian), một test `perf` mỏng dùng chung helper với trần ≥ 3× số đo (vd `LLEN_TIMEOUT_S + 2.2`) | B5-06c, B5-07, B6-03b |
| F6 | P2 | R-34, [6] E | Việc sót không có dòng nợ: (a) `W7/C26/quyet-dinh.md:14` "Việc còn lại để điều phối: revision contract … drop `ck_dataset_versions_failure_code`" (NO-275) — không có trong `DEBT.md`/`docs/fixes.md`; (b) NO-304 ghi "còn `_STORAGE._factory` riêng tư" nhưng phần sót thật là `tasks._STORAGE.override` / `tasks._storage()` gọi từ test (`apps/worker/pipeline_quality/tests/test_runtime.py:54`, `test_service.py:322`) — không dòng nợ | như bên | (a) chốt bằng mã: CHECK cũ vẫn lo định dạng nên không cần contract — xoá câu "việc còn lại" và ghi lý do vào FIX-273, hoặc làm revision contract ngay; (b) mở API công khai (vd `override_quality_storage`) cho test, đóng NO-304 đủ | DEBT-02 (điều phối) / B5-07 |
| F7 | P3 | K24, R-19 | `a7e3019` (FIX-320) nới `skip_type == "pytest.xfail"` thành `endswith(".xfail")` và viết test `type="pytest.{"xfail"}"` chỉ để né grep [11].3 — grep vẫn bắt `.xfail` (MF/buoc4 ghi dương tính giả) | `tools/case_gate.py:262`, `tools/tests/test_case_gate.py:341` | Hoàn `== "pytest.xfail"`, ghi hai dòng vào danh sách dương tính giả của audit | B0-01 |
| F8 | P3 | LOG-xx | `reply = json.loads(...)` rồi `reply.get("code")`: dòng `ML_EVAL_RESULT null`/`[]`/`5` → `AttributeError` thô; `float(value)` không bọc | `apps/ml/ml_eval/tasks.py:96-108` | `if not isinstance(reply, dict): reply = {}`; `float()` lỗi → `MODEL_FORMAT_UNSUPPORTED`; thêm 2 ca test | B6-04b |
| F9 | P3 | LOG-xx | `stdout.write(RESULT_PREFIX + …)` không có `"\n"` đầu: thư viện C ghi fd 1 không xuống dòng → dòng gộp trượt `startswith` | `apps/ml/ml_eval/sandbox.py:87` | Ghi `"\n" + RESULT_PREFIX + …` | B6-04b |
| F10 | P3 | TEST-xx (assert lỏng) | `pytest.raises(AppError)` không khẳng định mã (NO-230 503 vs `INTERNAL`), docstring nói `AccessDenied` mà MinIO trả `SignatureDoesNotMatch` | `packages/storage/tests/test_s3.py:279,290` | `as exc` + `assert exc.value.code …`; sửa docstring | B0-04 |
| F11 | P3 | TEST-xx (assert lỏng) | `unrounded = padded_input[..., :max(resized, REC_MIN_WIDTH_PX)]` — khi `resized ≤ 320` so một mảng với chính nó | `apps/ml/text/tests/test_reader_real.py:177` | Bỏ qua ca `resized <= REC_MIN_WIDTH_PX`, đo lại sàn `checked` | B5-04 |
| F12 | P3 | TEST-xx (assert lỏng) | Test NO-197 chỉ kiểm `access_log … if=$…` ở server, không kiểm `map $request_uri` có `default 1` và `files/ → 0` | `deploy/tests/test_nginx.py:576` | Assert cấu trúc `map` | B0-08 |
| F13 | P3 | TEST-xx (assert lỏng) | Chặn tái phát bằng quét chuỗi nguồn (`'.split("_", 1)' not in getsource`, `"measurements.locks" not in getsource`) | `apps/api/me/tests/test_text_source.py:14`, `apps/api/templates/tests/test_locks_source.py:8` | Thêm assert hành vi (`templates.service.lock_project_scope is packages.db.locks.lock_project_scope`; khoá avatar là ULID) | B1-04 / B2-07 |
| F14 | P3 | TEST-01 | Nhánh mới `existing is None` (dòng bị trim xoá giữa INSERT…DO NOTHING và SELECT) không test nào khẳng định | `apps/api/notifications/service.py:152-158` | Test Postgres thật xoá dòng giữa hai câu, khẳng định không publish, trả `None` | B4-02 |
| F15 | P3 | R-07 | `max_length=200` ghi tay, validator đọc `notifications_mark_max` (mặc định 200) — hai nguồn | `apps/api/notifications/schemas.py:41` | Một hằng chung cho cả settings mặc định và `Field` | B4-02 |
| F16 | P3 | R-07 | Tự gắn `before_cursor_execute` thay vì `count_sql()` có sẵn (`apps/api/projects/tests/sql_count.py:31`), lọc `"FROM floors"` bỏ sót JOIN | `apps/api/versions/tests/test_snapshots.py:421-437` | Dùng `count_sql()`, regex `(?:FROM|JOIN)\s+floors\b` | B3-04 |
| F17 | P3 | OBS-xx | Allowlist env của tiến trình con thiếu `LOG_LEVEL`/`LOG_JSON` → con luôn JSON/INFO | `apps/ml/training_runner/tasks.py:29-33` | Thêm hai khoá vào `_ENV_KEEP` + test | B6-03b |
| F18 | P3 | R-01 | Docstring nói "`sample_key` (không `dataset_object`, chỉ nhận tên một đoạn)" — sai từ FIX NO-263 (`keys.py:57` gọi `dataset_object`, nhận đường nhiều đoạn) | `apps/ml/training_runner/dataset.py:107` | Viết lại docstring | B6-03b |
| F19 | P3 | SEC-xx (che log) | Regex userinfo `[^\s/]+@` tham lam qua `?…@`: `redis://:pw@host?x=a@b` che cả host | `packages/core/logging.py:84` | `[^\s/?#]+@` + ca test | B0-02 |
| F20 | P3 | docs | Sổ sách lệch: `MF/dong-so-bang.tsv` NO-196 ghi `base.yml` đổi sang `${…:=…}` nhưng `base.yml:125,131` vẫn `:?` (diff rỗng); `duyet-nguoi-dung-2026-10-05.md` ghi "~18:35Z" trong khi `timeline.md:162` ghi duyệt 01:16Z; phạm vi H4-B (chỉ `limit_conn` streams, không `limit_req /api/files/`) chỉ có ở timeline, `BE-00.md:131` | các tệp bên | Sửa ghi chú NO-196, giờ duyệt, ghi phạm vi H4-B vào tệp duyệt | DEBT-02 (điều phối) |
| F21 | Nit | CASE (tên test) | Tên không theo `test_<hàm>__<điều kiện>` hoặc dùng `__` cho thứ không phải mã case: `training_runner/tests/test_slot.py::test_claim_lease_unexpected_error_marks_lost`, `projects/tests/test_routes_build.py:166`, `projects/tests/test_wire.py:107` (NO-195 gốc đòi đổi), `pipeline_steps/tests/test_sweep_rules.py:327,349`, `streams/tests/test_fixture_streams.py:394`, `deploy/scripts/tests/test_drill.py` (`…__no_c16b`, `…__w10`) | như bên | Đổi tên | chủ từng tệp |
| F22 | Nit | R-02 | Docstring sai/cũ: `pipeline_persist/tests/test_persist_lock.py:52-56` ("nợ ghi riêng" — thực là NO-296 ➖), `library/tests/test_jobs_cli.py:117` (3 gói, thực 5 `WORKER_BLOCKED`), `storage/tests/test_read_all_capped.py:34` | như bên | Sửa docstring | B5-06b, B2-06, B0-04 |
| F23 | Nit | DB-xx (nhất quán) | `3cba227` (FIX-260) sửa docstring `Create Date` của revision **đã gộp** `r20260925_b2_04_drawings.py`, trong khi NO-261 đóng ➖ phần migration với lý do "revision đã hợp nhất thì không sửa" — vô hại về schema nhưng hai quyết định ngược luật nhau | `packages/db/migrations/versions/r20260925_b2_04_drawings.py:5` | Hoàn `3cba227` (NO-219 chỉ cần mako mới cho revision sau) hoặc ghi rõ ngoại lệ "chỉ docstring" vào FIX-274 | B2-04 |
| F24 | Nit | OBS | `coverage_gate` in "100.00 %" cho đơn vị `deploy`/`tests` không có câu lệnh nào | `tools/coverage_gate.py:291-293` | Bỏ dòng khi `num_statements == 0` | B0-01 |

Đã soát và **đứng**: NO-186 ❌ (`_finish` tự bọc từ `eb40a3c`, tổ tiên `main`, trước ngày mở nợ; FIX-245 `raise first` không nuốt), NO-268 ❌
(`3e6ddc2`, `ab.log` 6 lượt A/B), NO-296 ➖ (`writer.py` `_LOG_CHUNK_ROWS`, `unnest … WITH ORDINALITY`, khoá 21 → 8,5–9,5 s,
trần 30 s ≥ 3×), NO-261 ➖ migration, NO-107/150/206/207/351 sửa thật (seed admin chỉ `dev/test/ci`; một head
`r20261004_b1_03_fix325`, hai revision expand thuần có `downgrade()`, không cần `docs/contracts.toml`), C48 `-n 6` (n4/n6/n8 = 571/505/513 s),
C47 FIX-338…345 (trừ F4), FIX-225 (log thật 1 272 passed; "1 failed" là lượt đỏ cố ý trên `main`), `7fb6e30` có trong `main..b017a58`.
[11].3: 7 dòng grep — 3 dương tính giả MF đã ghi + 2 `time.sleep` (vòng chờ khoá có hạn `apps/ml/runtime/lease.py`, dòng thụt lại
trong `test_start_cases.py`) + 2 từ F7; mọi `noqa`/`type: ignore` thêm (40 dòng) có mã + lý do. Merge sửa tay: 3 merge
(`725678d` docs/security, `ab8ba73`, `d81f493`) chỉ giải xung đột, không thêm hành vi. Commit hiến chương chỉ chạm tài liệu, có trailer
`Charter-Approved`; câu chữ khớp bản nháp trừ F4.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 3 (F4 P2) | 0,75 |
| CON – Đồng thời & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Đúng đắn | 15 % | 4 (F8, F9) | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & hợp đồng | 10 % | 3 (F3 P2) | 0,30 |
| TEST – Kiểm thử | 7 % | 3 (F5 P2) | 0,21 |
| OBS, OPS – Vận hành / quy trình | 5 % | 1 (F1 P1) | 0,05 |
| MNT – Bảo trì | 3 % | 3 (F2, F6 P2) | 0,09 |

Tổng: **3,75 / 5**

## PHÁN QUYẾT: REQUEST CHANGES

Mã các đợt W3–W10 sửa đúng gốc và có bằng chứng (cổng đầy đủ thoát 0, 23 test chặn tái phát tự chạy đỏ trên `main` → xanh trên nhánh,
quyết định ❌/➖ đã duyệt đều đứng), nhưng còn một **P1** chưa waiver: 14 commit có trailer `Prompt:`/`Fix:` mà git không đọc được, 11
trong số đó ghi sai chủ — gộp `--no-ff` sẽ ghi vĩnh viễn vào `main`. Để được APPROVE ở lượt 2 phải: (1) viết lại thông điệp 14 commit (F1);
(2) sửa F2–F6 (P2); (3) sửa F7–F24 (P3/Nit) trong cùng vòng sửa ([6] D.3); (4) lượt 2 chạy cổng theo R-33b (diff vòng sửa chạm
`deploy/backup`, `tools/case_gate.py` → bước 1–5 + test đích; F3 cần bước 8 với `VERIFY_BRANCH=integration`).
