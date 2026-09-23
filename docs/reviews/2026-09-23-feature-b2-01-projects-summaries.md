# Review merge feature/b2-01-projects-summaries → main

- Ngày: 2026-09-23 · Reviewer: phiên /merge-review (độc lập, R-37) · Commit đầu nhánh: `003d46ac4b6a`
- Cổng: `bash tools/verify/run.sh verify` mã thoát **0** (chạy tại chỗ, worktree `review-b2-01` @ `003d46a`, một lượt, attached)
- Độ phủ: tổng dòng **99,08%** · nhánh **97,71%** — `apps/api/projects` 97,74% / 96,15%; `packages/db` 95,05% / 95,45%; `packages/testing` 99,26% / 100,00%; tập file bị chạm 97,93% / 96,34%
- Test: **3021 qua / 0 hỏng / 4 deselected** (436 s)
- Phạm vi: `git diff main...HEAD` — 35 file, 4510 dòng thêm, 0 dòng xoá; toàn bộ thuộc whitelist B2-01. Squash `d461ec8` (FIX-073…078) đã review riêng, **không** chấm lại.

## Bảng cổng (E.10, nguyên văn từ mã thoát thật)

```
  # | Bước                         | Trạng thái     | Chi tiết
------------------------------------------------------------------------------------------
  0 | làm ấm node_modules          | đạt            | /work/contract-node/3c583539a0314ecd
  1 | ruff format --check          | đạt            |
  2 | ruff check                   | đạt            |
  3 | mypy --strict                | đạt            |
  4 | lint-imports                 | đạt            |
  5 | coverage run -m pytest → coverage_gate | đạt            |
 5b | pytest -m perf → case_gate   | đạt            | perf: 0 đơn vị bị chạm
  6 | lint_migrations → migrate_check | đạt            |
  7 | H1 H3 H4 H5 (tools.contract.check) | đạt            |
  8 | openapi                      | đạt            |

mã thoát: 0
```

Bước 6: `migrate_check` đạt trọn 10 mục (1 head, downgrade -1, downgrade base, model khớp DB, tên CHECK khớp model).
Bước 7: H1 đạt 276 mẫu, H3 đạt 10 khoá/3 vai; H4/H5 `không áp dụng` **đúng luật** BE-00 §12 (B3-05, B4-01 chưa hợp nhất — không có `changes/B3-05.md`, `changes/B4-01.md`).
Bước 5b: `case_gate: đạt`, 6 `op` của B2-01 đủ case; C16 của `projects_delete_project` được miễn hợp lệ trong `apps/api/projects/cases.toml` ("DELETE không có thân"). Ba cảnh báo còn lại (`files_read_object`, `health_live`, `health_ready`) thuộc B0-06/B0-08.

## Điều kiện dừng sớm (§2) — không cái nào dính

Cây sạch · `changes/B2-01.md` có · mọi dòng đầu commit đúng Conventional Commits và có trailer `Prompt: B2-01` · diff **không** đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pyproject.toml` gốc, `.importlinter`, `conftest.py` gốc · **không** `pragma: no cover`, `pragma: no branch`, `skip`/`xfail` mới, không hạ ngưỡng · hai `# type: ignore` đều có mã (`[arg-type]`), hai `# noqa: S603` đều có mã **và** lý do.

## Soát trọng tâm — đã tự kiểm, đạt

- **K08 / `require_project`** (`apps/api/projects/access.py:57-77`): resolver chạy trước (lỗi của nó thắng); `project_from_path` 404 `resource:"project"` **không** truy vấn khi sai mẫu `prj_`+ULID; **một** câu JOIN `projects`×`project_memberships` kiểm cả "chưa xoá" lẫn "là thành viên"; 404 **trước** 403 trong `_checked_access`; khoá `SYSTEM_SCOPED_KEYS`/khoá lạ → `ValueError` lúc khai route. `permission_dependency` chỉ gắn metadata (`apps/api/core/permissions.py:28-40`), **không** chặn trước thân dependency — nên thứ tự 404→403 là thật. Test: `test_system_admin_not_member_is_not_found`, `test_bad_project_id_pattern_is_not_found_without_query`, `test_resolver_error_wins_before_membership_check`, `projects_read_project__C06` (admin không phải thành viên), `projects_update_project__C07` / `projects_delete_project__C07` (viewer).
- **K05 / mass assignment**: `created_by=principal.user_id` (`service.py:216`), không từ thân; `EDITABLE_FIELDS` chỉ `name|code|address`; `status`, `members`, `progress`, `currentVersion` khai `JsonValue` ở `schemas.py:96-101` để lọt `extra="forbid"` rồi **không** hàm nào đọc. Test `test_create_project_ignores_status_members_progress_current_version`, `test_role_in_request_body_is_ignored`.
- **C18 / giao dịch**: `record_activity` cùng session, không `commit` trong service (`AppRoute` commit/rollback); hook `project.create_floors` ném → dự án + membership + nhật ký cùng biến mất (`test_create_project_hook_error_rolls_back_project_and_membership`); #26 `{}` và #26 gửi lại giá trị cũ đều không đổi `updatedAt`, không nhật ký; #27 giữ dòng membership mà chặn truy cập ngay (`test_delete_project_keeps_membership_row_but_revokes_access`).
- **PERF-01**: #23 và N1 đều **3 câu** cho 1 và 20 dự án (`test_*_query_count_is_constant_across_batch_size`, bộ đếm `tests/sql_count.py` nghe `Engine.before_cursor_execute`). `project_rollups` đúng **một** `GROUP BY`, `.where(hidden.is_(False))`; công thức `status`/`legacy_status`/`default_floor_id`/`COALESCE(SUM(area_m2),0)` khớp từng chữ khối [6]. Bất biến refine giữ được: `floor_count == 0` ⇔ không có dòng ⇒ `_EMPTY_ROLLUP` ⇒ `defaultFloorId` vắng; `qc` đòi `floor_count > 0` ⇒ `array_agg(...)[1]` không NULL. `areaM2` là `float` sau `quantize(0.01, ROUND_HALF_UP)`.
- **CON-01 / CON-07**: `remove_user_from_all_projects` khoá `ORDER BY project_id ... FOR UPDATE` trước khi xoá rồi mới `touch_project`; `lock_editor_ids` dùng `with_for_update(of=ProjectMembership)` (không khoá `users`); `touch_project` (`projects`) luôn là lời khoá **mới** cuối cùng của mọi lượt ghi — đúng thứ tự BE-00 §7. Hai lượt `UPDATE … WHERE deleted_at IS NULL RETURNING` của #26/#27 là ghi có điều kiện một câu, không read-modify-write.
- **K36 / lịch dọn**: `_select_batch` dùng session riêng và đóng **trước** khi gọi kho; session thứ hai `SET LOCAL statement_timeout`/`lock_timeout` (giá trị là `PositiveInt` của settings, không phải dữ liệu người dùng); kho hỏng → giữ dòng; chỉ bắt `DBAPIError` và chỉ nuốt khi `translate_db_error` trả `DEPENDENCY_UNAVAILABLE`, còn lại ném lại (`test_handle_delete_error_reraises_non_infra_db_errors`); **không** `except Exception`. Nhập trễ `create_storage` trong `purge_deleted_projects()` là hợp lệ và cần thiết — `minio/__init__.py` kéo `argon2`, nhập ở đầu file sẽ phá `api-jobs-no-web`.
- **Ranh giới nhập**: `test_boundary_data.py`, `test_boundary_jobs.py` nhập `memberships`, `summaries`, `jobs` trong **tiến trình con** với `fastapi`/`starlette`/`jwt`/`argon2` bị chặn — bước 4 `lint-imports` cũng đạt.
- **Migration (DB-01…05)**: `r20260923_b2_01_projects` expand thuần (3 `create_table` + 1 index, không đụng bảng cũ); CHECK `walls_reviewed >= 0 AND walls_reviewed <= walls_total`, CHECK `pipeline_state IN (…)`, mọi FK tới `projects.id` là `ON DELETE CASCADE` — đúng khối [5] và có test quét `test_every_fk_to_projects_cascades`; `downgrade()` bỏ bảng theo thứ tự ngược; hằng chép tay, không nhập model; 1 head.
- **R-01/R-07/R-08**: mọi hàm (kể cả hàm lồng và hàm test) có docstring; hàm dài nhất `project_rollups` 47 dòng, không hàm nào > 50 dòng, không lồng > 3 cấp; `_checked` dùng chung cho ba chỗ "0 dòng → 404" là gộp trùng lặp đúng R-07.
- **Việc tách logic hậu-`await` ra hàm sync (NO-130)**: kiểm từng hàm tách (`_checked`, `_changed_fields`, `_project_outs`, `_summary_page`, `_summaries_stmt`, `_checked_access`, `_handle_delete_error`) — đều là đơn vị có tên đúng nghĩa, đọc **dễ hơn** bản lồng, không chỗ nào đổi ngữ nghĩa. Không phải finding.
- **Test**: C06 dùng admin hệ thống không phải thành viên, C07 dùng viewer là thành viên; golden N1 phủ đủ `processing` / `qc` / `done` / 0 tầng / `area` NULL (`test_routes_read.py:152-214`); test đồng thời thật cho khoá dòng (`test_locked_membership_row_defers_only_that_project`); không mock Postgres/MinIO (dùng `ephemeral_minio`, `LocalDiskStorage` thật).

## Sổ nợ (§5)

Bốn nợ tác giả nêu đều **đã có dòng** trên `main`: NO-130 (P2, chủ B0-01), NO-135 (P3, `avatarUrl`), NO-136 (P3, `_checked(None)`), NO-137 (P3, `project_name`). Lý do đứng được, không có nợ P0/P1 mở. Bảy nợ ngoài phạm vi (NO-126…NO-134) đã đóng ở `3f67f1c`.

Bảy mục "Lệch khỏi prompt" của báo cáo — **đối chiếu từng mục, cả bảy chấp nhận được**:
1. `UserRow`→`User`: tên thật trong `packages/db/models/auth.py`, prompt [3] cho phép. ✔
2. Thân lỗi W7 phẳng: xác nhận ở `apps/api/core/errors.py:79-86` (`{"code","requestId", **wire_params}`) — giả định `body["params"]` của việc T sai, sửa đúng. ✔
3. Thêm `test_projects_create_project__C17`: khối [8] đòi C17, `case_gate` xác nhận có. ✔
4. Cổng quyền ở `dependencies=`: khối [7] không quy định vị trí; lý do (C10/C22 của B0-06 ghi đè cổng bằng `lambda: None`) đúng với `require_role`/`require_permission` của B1-02; hệ quả `project_name` chưa dùng đã ghi NO-137. ✔
5. #26 `record_activity` rồi `touch_project`: đúng nguyên văn khối [6]. ✔
6. Tách nhánh ra hàm sync: bắt buộc vì NO-130, không làm mã khó đọc (xem trên). ✔
7. `_checked` dùng chung: R-07. ✔

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | RES-02 | `run_project_purge` lặp vô hạn khi cả một lô hỏng: vòng chỉ thoát ở `len(ids) < batch`, mà `_select_batch` chọn lại **đúng** tập cũ (`deleted_at < cutoff ORDER BY id LIMIT batch`, `cutoff` tính một lần) và dự án hỏng vẫn còn dòng. Kho hoặc DB hỏng + ≥ `PROJECT_PURGE_BATCH` (mặc định 20) dự án quá hạn ⇒ 20 dự án đầu đều trả `False`, `len(ids) == batch`, chọn lại chính 20 dự án ấy, mãi mãi — thử lại không trần, không backoff. Docstring `jobs.py:94-95` khẳng định "mỗi lượt gọi tự dừng theo dữ liệu" là **sai**. Hai test hiện có không chạm case này: `test_storage_failure_keeps_row_and_logs` mồi 1 dự án với `batch=10`, `test_purge_batches_until_exhausted` không có lượt hỏng nào | `apps/api/projects/jobs.py:99-105` | Phân trang keyset: `_select_batch(..., after)` lọc `Project.id > after`, vòng ngoài giữ `after = ids[-1]` — dự án hỏng bị bỏ qua ở lượt sau thay vì chọn lại; hoặc `break` khi một lô không xoá được dự án nào. Test cần thêm: mồi `batch + 1` dự án quá hạn với kho luôn ném → `run_project_purge` trả 0 và **kết thúc** |
| 2 | P2 | MNT-05 | Nhánh 4510 dòng thêm (~1600 dòng ngoài test) — vượt trần 400 dòng logic | `git diff main...HEAD --stat` | **Không đáng tách thêm**: đúng bằng danh sách [10] của một prompt và đã dựng qua 5 nhánh con N/D/A/T/M có báo cáo riêng. Ghi nhận, không đòi sửa |
| 3 | P3 | PERF-01 | `touch_project` chạy trong vòng lặp: một `UPDATE` cho mỗi dự án của người bị gỡ | `apps/api/projects/memberships.py:155-156` | Gộp thành một câu `update(Project).where(Project.id.in_(locked)).values(updated_at=clock.now())`. Đường lạnh (xoá/vô hiệu người dùng), không chặn |
| 4 | P3 | PERF-02 | Lô rỗng vẫn gửi 2 câu `… IN ()`: `member_users` và `project_rollups` không chặn `project_ids` rỗng, nên một trang N1 rỗng vẫn tốn 3 vòng DB | `apps/api/projects/service.py:127-128`, `:193-194` | `if not project_ids: return {}` ở đầu `member_users`/`project_rollups` |
| 5 | P3 | MNT-04 | `changes/B2-01.md` lỗi thời ở `HEAD`: vẫn ghi "Chưa có endpoint ở lớp này… **bước 7 (golden/hợp đồng) và bước case chưa áp dụng cho nhánh này**", trong khi 6 `op` đã mount, H1 chạy 276 mẫu và `case_gate` chấm đủ 6 `op`. Không ảnh hưởng cổng (cổng chỉ đọc **tên file**, `tools/charter.py:148`), nhưng sai với BE-00 §13.2 | `changes/B2-01.md:8` | Viết lại gạch đầu dòng cuối: 6 route đã mount, bước 7 và bước case **đã áp dụng và đạt** |
| 6 | Nit | R-24 | `# type: ignore[arg-type]` có mã nhưng không có lý do cùng dòng | `apps/api/projects/tests/test_access.py:110`, `:222` | Thêm lý do ngắn: cố tình truyền khoá sai kiểu để kiểm `ValueError` |

P0: 0 · P1: 1 · P2: 1 · P3: 3 · Nit: 1

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 4 | 0,40 |
| RES – Chịu lỗi | 10% | 1 | 0,10 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 4 | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 3 | 0,09 |
| **Tổng** | **100%** | | **4,37 / 5** |

## PHÁN QUYẾT: REQUEST CHANGES

Chất lượng nhánh cao và đều: cổng đầy đủ xanh thật (mã thoát 0, 8/8 bước, 3021 test, độ phủ mọi gói bị chạm ≥ 95%), K08/K05/C18/PERF/CON/migration đều tự kiểm được bằng mã và test trong diff, bảy mục "Lệch khỏi prompt" của tác giả đều chấp nhận được, sổ nợ đầy đủ. Điểm 4,37 tự nó đủ ngưỡng `APPROVE`; nhưng ma trận §5 của `RULE.md` chặn merge khi còn một P1 chưa waiver, và finding 1 là một P1 thật: `run_project_purge` không có bảo đảm tiến triển, cả một lô hỏng thì việc nền lặp lại đúng lô ấy không trần, không backoff, cho tới khi Celery giết theo `task_time_limit` (3600 s) rồi beat lại bắn lượt mới sau một giờ — đúng dạng "retry storm" mà RES-02 cấm, và đúng cái mà docstring của chính hàm khẳng định là không thể xảy ra.

**Để được `APPROVE`, chỉ cần một việc:** sửa finding 1 (phân trang keyset theo `Project.id > after`, hoặc `break` khi một lô không xoá được dự án nào) **và** thêm một test mồi `batch + 1` dự án quá hạn với kho luôn hỏng, chứng minh hàm kết thúc và trả 0; rồi chạy lại `bash tools/verify/run.sh verify` một lượt attached. Finding 2 chỉ ghi nhận. Finding 3, 4, 5, 6 là P3/Nit — tác giả tự quyết sửa ngay hay ghi `DEBT.md`, **không** chặn merge; nếu hoãn thì finding 3, 4, 5 cần mỗi cái một dòng `NO-<nnn>` (R-34).
