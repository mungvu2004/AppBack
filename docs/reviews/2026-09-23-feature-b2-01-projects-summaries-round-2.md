# Review merge feature/b2-01-projects-summaries → main — lượt 2

- Ngày: 2026-09-23 · Reviewer: phiên `/merge-review` (độc lập, R-37) · Commit đầu nhánh: `b4841abbbc0e`
- Lượt 1: `docs/reviews/2026-09-23-feature-b2-01-projects-summaries.md` — **REQUEST CHANGES** (4,37/5), 1 P1 + 1 P2 + 3 P3 + 1 Nit
- Phạm vi chấm lại: `git diff 003d46a..HEAD` — 3 commit, 8 file, **186 dòng thêm / 22 dòng xoá**. Phần đã duyệt ở lượt 1 (`main...003d46a`) **không** chấm lại.
- Cổng: `bash tools/verify/run.sh verify` mã thoát **0** (chạy tại chỗ, worktree `review-b2-01-r2` @ `b4841ab`, **một** lượt, attached; container `appback-verify-review-b2-01-r2-verify-run-e207885a5464`, `docker wait` → 0)
- Test: **3026 qua / 0 hỏng / 4 deselected** (465,45 s) — đúng **+5 test** so với lượt 1 (3021)
- Độ phủ: tổng dòng **99,09%** · nhánh **97,67%**; `apps/api/projects` **98,10% / 96,43%** (lượt 1: 97,74% / 96,15%); `packages/db` 95,05% / 95,45%; `packages/testing` 99,26% / 100,00%; tập file bị chạm 98,26% / 96,59%. Mọi gói bị chạm và tổng đều ≥ 90% dòng **và** nhánh.

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

Bước 5b: `case_gate: đạt`, 6 `op` của B2-01 đủ case (C16 của `projects_delete_project` miễn hợp lệ trong `cases.toml`); ba cảnh báo còn lại thuộc B0-06/B0-08. Bước 6: `lint_migrations` đạt 6 revision, `migrate_check` đạt trọn 10 mục. Bước 7: H1 276 mẫu, H1 ngữ cảnh 10 mẫu, H3 10 khoá/3 vai; H4/H5 `không áp dụng` **đúng luật** BE-00 §12 (B3-05, B4-01 chưa hợp nhất). Không bước nào "chưa chạy".

## Điều kiện dừng sớm (§2) — không cái nào dính

Cây sạch (`git status --porcelain` rỗng) · `changes/B2-01.md` có · ba dòng đầu commit đúng Conventional Commits, 63–65 ký tự, mỗi commit có trailer `Prompt: B2-01` · diff **chỉ** chạm `apps/api/projects/**` và `changes/B2-01.md` — không đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pyproject.toml` gốc, `.importlinter`, `conftest.py` gốc · **không** `pragma: no cover`, `pragma: no branch`, `skip`/`xfail` mới, không hạ ngưỡng · quét lại toàn nhánh: hai `# type: ignore[arg-type]` nay **có cả mã và lý do**, hai `# noqa: S603` có mã và lý do.

## Kiểm từng finding của lượt 1

### Finding 1 (P1, RES-02, NO-138) — đã sửa tận gốc

`apps/api/projects/jobs.py:41-54` + `:97-119`. Phân trang keyset đúng như yêu cầu:

- `_select_batch(..., after)` thêm `.where(Project.id > after)` khi `after is not None`, giữ nguyên `ORDER BY id`, `LIMIT batch`; vòng ngoài giữ `after = ids[-1]` sau mỗi lô đầy.
- **Bảo đảm tiến triển, tự kiểm bằng mã:** `ids` của lô sau chỉ chứa id **lớn hơn** `ids[-1]` của lô trước, nên mốc `after` tăng ngặt mỗi vòng và tập id được duyệt là một phân hoạch của `{id : deleted_at < cutoff}`. Vòng chạy tối đa `ceil(N/batch) + 1` lần bất kể bao nhiêu dự án hỏng — không còn đường nào chọn lại đúng lô cũ.
- **Mỗi dự án đúng một lần mỗi lượt:** dự án xoá được thì biến mất; dự án hỏng vẫn còn dòng nhưng id của nó `<= after`, nên `_select_batch` sau đó loại nó. Đây chính là ngữ nghĩa docstring mới khẳng định — và lần này docstring **khớp** mã (lượt 1 thì không).
- **Vẫn xoá hết khi không lỗi:** `batch=2`, 5 dự án → `[p1,p2]` xoá, `after=p2`; `(p2,…]` → `[p3,p4]` xoá, `after=p4`; `(p4,…]` → `[p5]`, `len < batch`, dừng. Tổng 5 — `test_purge_batches_until_exhausted` (có sẵn, `batch=2`, khẳng định `== 5`) vẫn xanh, nên keyset **không** làm sót dự án nào ở đường sạch.
- Hệ quả duy nhất, đã ghi trong docstring: dự án xoá mềm **trong lúc** một lượt đang chạy mà id nhỏ hơn `after` phải đợi lượt lịch sau (`EVERY = 1 h`). `cutoff` tính một lần đầu lượt nên nó vốn đã không thuộc lượt này — không phải hồi quy.

**Hai test mới, đều có thời hạn và đều thật sự tái hiện lỗi cũ** (`apps/api/projects/tests/test_jobs.py:136-220`):

- `test_purge_does_not_loop_when_a_whole_batch_fails` — `batch = 2`, mồi `batch + 1 = 3` dự án quá hạn, khoá `FOR UPDATE` dòng `project_memberships` của **cả ba** (FK `ON DELETE CASCADE` buộc `DELETE FROM projects` khoá dòng con), `PROJECT_PURGE_LOCK_TIMEOUT_S=1` ⇒ mọi dự án đều `lock_timeout`. **Đỏ trên `003d46a`, tự kiểm bằng mã:** `_select_batch` bản cũ không có `after`, nên lô đầu trả `[p1,p2]`, cả hai hỏng, không dòng nào biến mất, `len(ids) == batch` ⇒ chọn lại đúng `[p1,p2]` vô hạn, `p3` không bao giờ tới; `asyncio.wait_for(..., LOOP_TIMEOUT_S=60)` cắt và test **hỏng** chứ không treo cổng (đúng BE-00 §12 "trần thời gian").
- Khẳng định `sorted(_purge_failed_ids(caplog)) == [p.id for p in projects]` là bằng chứng kép: đủ **ba** id (keyset tiến tới lô thứ hai, không dừng sớm) và **không id nào lặp** (mỗi dự án đúng một lần thử mỗi lượt).
- `test_purge_skips_failed_projects_and_finishes_later_batches` — 5 dự án, khoá dự án thứ 1 và thứ 4 (một ở mỗi lô), khẳng định 3 dự án còn lại **bị xoá** và 2 dự án khoá **còn**. Phủ đúng chỗ keyset dễ sai nhất: lô sau phải bỏ qua dự án hỏng của lô trước mà vẫn xoá hết phần còn lại.
- Cả hai dùng Postgres thật, khoá thật, `LocalDiskStorage` thật — không mock dịch vụ (K23). `reset_projects_settings_cache()` gọi trong `finally` **trước** khi `monkeypatch` gỡ biến môi trường, nên không rò cache sang test sau.

### Finding 3 (P3, PERF-01) — đã sửa

`summaries.py:159-172` thêm `touch_projects` (một `UPDATE … WHERE id IN (…)`), `touch_project` **uỷ quyền** cho nó (`touch_projects(db, project_ids=(project_id,), …)`) nên luật chỉ có một bản (R-07), không có bản sao để lệch nhau. `memberships.py:162` thay vòng lặp bằng một lời gọi. `touch_project` vẫn có hai caller thật (`service.py:237`, `:265`) — không phải dead code.

**Thứ tự khoá BE-00 §7 giữ nguyên:** `remove_user_from_all_projects` vẫn khoá `project_memberships … ORDER BY project_id FOR UPDATE` **trước**, `DELETE` membership, rồi mới chạm `projects` — `touch_projects` vẫn là **lời khoá mới cuối cùng** của lượt ghi, đúng bậc thang "… `project_floor_summaries` → `projects`". Danh sách `locked` sinh từ chính câu khoá ấy, không phải dữ liệu người dùng.

Test `test_remove_user_from_all_projects_does_not_scale_sql_with_project_count` (`test_memberships.py:163-178`) là test hồi quy thật, không phải test trang trí: với mã cũ 1 dự án = 4 câu và 5 dự án = 8 câu ⇒ `big.count == small.count` **đỏ**; với mã mới cả hai = 4.

### Finding 4 (P3, PERF-02) — đã sửa

`memberships.py:101-102` và `summaries.py:202-203`: `if not project_ids: return {}`. **Không đổi response**, tự kiểm bằng mã: hai hàm vốn khởi tạo `{pid: [] …}` / `{pid: _EMPTY_ROLLUP …}` rồi mới nhét kết quả, nên với `project_ids` rỗng thân cũ cũng trả đúng `{}` — lối tắt mới đồng nhất giá trị, chỉ bỏ vòng DB. `_project_outs` / `_summary_page` chỉ đọc `members[id]`, `rollups[id]` khi có dự án, nên `{}` không sinh `KeyError`. `_floor_parts` vốn đã không truy vấn khi chưa ai cắm cổng `project.floors`.

Test `test_empty_page_runs_only_the_project_query` (`test_routes_build.py:149-159`, parametrize `#23` và `N1`) khẳng định **đúng 1** câu SQL cho người chưa có dự án nào — với mã cũ là 3.

### Finding 5 (P3, MNT-04) — đã sửa

`changes/B2-01.md:8` nay ghi 6 route `#23`–`#27` + `N1` đã mount và "bước 7 và bước case **đã áp dụng và đạt**". Khớp với cổng vừa chạy: `case_gate` chấm đủ 6 `op` của B2-01, bước 7 đạt 276 mẫu H1.

### Finding 6 (Nit, R-24) — đã sửa

`test_access.py:110` và `:222`: hai `# type: ignore[arg-type]` nay có lý do cùng dòng. Quét lại toàn nhánh không còn `type: ignore`/`noqa` nào thiếu mã hoặc thiếu lý do.

### Finding 2 (P2, MNT-05) — giữ nguyên trạng thái "chấp nhận"

`NO-139` đã `➖` với lý do đứng được (khối [10] định nghĩa một đơn vị bàn giao). Lượt 2 chỉ thêm 186 dòng, không làm tình hình xấu đi.

## Finding lượt 2

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | CON-01 | `touch_projects` đổi thứ tự khoá **dòng** trong bảng `projects` từ "tăng dần theo `project_id`" (vòng lặp cũ, `locked` đã `ORDER BY project_id`) sang "thứ tự do kế hoạch Postgres chọn" (một `UPDATE … WHERE id IN (…)` có thể là index scan hoặc bitmap heap scan tuỳ kích thước danh sách). Hai giao dịch cùng gọi `remove_user_from_all_projects` cho **hai người khác nhau** có ≥ 2 dự án chung, nếu rơi vào hai kế hoạch khác nhau, về lý thuyết có thể deadlock. Thứ tự **bảng** của §7 thì vẫn đúng (membership → `projects`), và `remove_user_from_all_projects` hiện **chưa có caller sản phẩm** nào (chỉ test gọi), nên chưa có đường chạy thật | `apps/api/projects/memberships.py:162`, `apps/api/projects/summaries.py:167` | Không chặn, không đòi sửa bây giờ. Khi B1-x cắm nó vào luồng xoá/vô hiệu người dùng: hoặc `SELECT id … WHERE id = ANY(:ids) ORDER BY id FOR UPDATE` trước `UPDATE`, hoặc ghi một dòng `NO-<nnn>` để người chủ luồng ấy cân nhắc |
| 2 | Nit | R-19 | `count_projects_of_users` (`memberships.py:115-126`) là **anh em cùng khuôn** với hai hàm vừa sửa ở finding 4 — cũng `IN (user_ids)` không chặn lô rỗng, cũng khởi tạo dict mặc định rồi nhét kết quả. Vòng sửa vá đúng hai chỗ reviewer chỉ tên mà bỏ chỗ thứ ba cùng lỗi trong **cùng file**. Hiện chưa có caller nên chưa tốn vòng DB nào | `apps/api/projects/memberships.py:115` | Một dòng `if not user_ids: return {}` cho đồng nhất, hoặc bỏ qua có ý thức — không chặn merge |

P0: **0** · P1: **0** · P2: **0** · P3: **0** · Nit: **2**

## Sổ nợ (§5)

- `NO-138` (P1, RES-02) đang ở trạng thái `🔧 đang sửa` trên `main` — **vòng sửa này đã đóng nó bằng mã và test**; người điều phối đóng dòng (`✅`, ngày 2026-09-23, trỏ `ecc4dae`) khi merge. Phiên review không sửa `DEBT.md`.
- `NO-139` (P2, MNT-05) `➖ chấp nhận`, lý do đứng được.
- `NO-135`, `NO-136`, `NO-137` (P3) vẫn `⬜ mở`, đều có chủ và đều không chặn — không còn nợ P0/P1 mở của nhánh này (R-35, R-38).
- Hai Nit của lượt 2 **không** bắt buộc có dòng `DEBT.md`; tác giả tự quyết.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 5 | 0,35 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 | 0,12 |
| **Tổng** | **100%** | | **4,97 / 5** |

RES 1 → 5: lỗi duy nhất của miền đã sửa tận gốc (bảo đảm tiến triển bằng keyset) chứ không vá triệu chứng bằng trần vòng lặp — đúng R-19. PERF 4 → 5 và TEST 4 → 5: cả hai P3 hiệu năng đều sửa kèm test hồi quy **đỏ trên mã cũ**, không phải test trang trí. MNT 3 → 4: MNT-04 đã sửa, MNT-05 vẫn là nợ chấp nhận nên chưa đầy điểm.

## PHÁN QUYẾT: APPROVE

Vòng sửa làm đúng, đủ và không thừa. P1 duy nhất của lượt 1 được chữa bằng đúng cách reviewer đề xuất và là cách đúng — phân trang keyset cho vòng lặp một bảo đảm tiến triển thật, tự kiểm được từ mã (mốc `after` tăng ngặt ⇒ vòng dừng sau tối đa `ceil(N/batch) + 1` lượt bất kể bao nhiêu dự án hỏng), chứ không phải một trần thử lại che triệu chứng; docstring nay khớp hành vi thay vì mâu thuẫn với nó. Hai test mới là test thật: đều dựng "dự án hỏng" bằng khoá `FOR UPDATE` trên Postgres thật, đều có `asyncio.wait_for` nên hồi quy làm test **hỏng** chứ không treo cổng, và khẳng định `sorted(_purge_failed_ids(...))` chứng minh cả "vòng lặp tiến" lẫn "mỗi dự án đúng một lần" — chính hai tính chất mà lượt 1 đòi. Ba P3 và Nit còn lại cũng đã sửa: `touch_projects` gộp một `UPDATE` mà **không** phá thứ tự khoá §7 (`projects` vẫn là lời khoá mới cuối cùng), lối tắt lô rỗng đồng nhất giá trị trả về nên không đổi response, `changes/B2-01.md` và hai `# type: ignore` đã đúng luật.

Cổng đầy đủ xanh thật: một lượt `bash tools/verify/run.sh verify` attached, mã thoát **0**, 8/8 bước `đạt`, không bước nào "chưa chạy"; 3026 test qua (đúng +5 so với lượt 1), độ phủ `apps/api/projects` tăng 97,74% → 98,10% dòng và 96,15% → 96,43% nhánh, mọi gói bị chạm ≥ 95% cả hai chỉ số. Không còn P0/P1/P2/P3; hai mục còn lại là Nit và không chặn merge. Điểm 4,97 ≥ 4,0 và không có P1 chưa waiver ⇒ ma trận `RULE.md` §5 cho `APPROVE`.

**Việc của người điều phối khi merge** (không phải của tác giả): đóng `NO-138` trong `DEBT.md` (`✅`, ngày đóng 2026-09-23, trỏ `ecc4dae`) vì nó đang ở `🔧 đang sửa`; squash vào `main` rồi xuất lại `openapi.json` ở gốc trước khi chạy bước 8 của `main`.
