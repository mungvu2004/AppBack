# Review merge fix/b0-01-fast-verify → main

- Ngày: 2026-09-22 · Reviewer: phiên /merge-review (độc lập) · Commit đầu nhánh: 5f254f775eb6
- Phạm vi: FIX-071 `f18546a` (bước 5 theo vùng bị ảnh hưởng), FIX-072 `e73af37` (khởi động nhanh, volume chung),
  `5f254f7` (BE-00 §12, ENV §2, CLAUDE.md). 18 file, +980/−41.
- Cổng: `bash tools/verify/run.sh verify --full` **mã thoát 1** (chạy tại chỗ; log container
  `.cache/src-out/verify/20260922T161713Z-5f254f775eb6.log` của worktree; 408 s)
  - Bước 0–4 đạt · **bước 5 hỏng**: `8 failed, 2415 passed, 10 skipped` · 5b, 6, 7, 8 chưa chạy.
- Độ phủ: không có số — bước 5 dừng ở pytest, `coverage_gate` chưa chạy.
- Khởi động `run.sh shell` ấm (lệnh `echo hi`): lượt 1 4,7 s, **lượt 2 3,9 s** (tác giả báo 5,99 s ấm) — khớp.

## Tự thử `affected()` (trong `run.sh shell`, cây `5f254f7`)

| File đổi | Kết quả |
|---|---|
| `tools/ci/x.py` | 8 thư mục (đơn vị `tools` → mọi test `tools/**` + đơn vị import `tools`) |
| `packages/storage/local.py` | 10 thư mục: storage, api/{access,auth,core,files,health}, ml/runtime, testing/golden, tools |
| `packages/core/ids.py` | 17 thư mục — gần như mọi đơn vị |
| `uv.lock`, `.github/workflows/ci.yml`, `docs/contracts.toml`, `setup.py` | `None` (chạy đủ) |
| `README.md` gốc | `[]` (0 test) |
| `deploy/docker/api.Dockerfile` | `deploy/tests` |
| `apps/api/auth/verifier.py`, `apps/api/auth/router.py` | **chỉ** `apps/api/access/tests`, `apps/api/auth/tests`, `packages/testing/golden/tests` |
| `scope_of`: `(None,worker)`→affected · `(full,worker)`→full · `(None,integration)`→full · `(affected,integration)`, `(bogus,worker)` → `ValueError` | đúng |

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P1 | TEST-03 / K25 | Test mới không cô lập khỏi `VERIFY_SCOPE` của tiến trình: `run.sh verify --full` đặt `VERIFY_SCOPE=full` cho container, 8 test kỳ vọng phạm vi mặc định nên hỏng — **chính lệnh mà hiến chương mới bắt reviewer/nhánh đi review chạy luôn đỏ**. Bằng chứng: `test_run_sh.py::test_verify_không_cờ_không_đặt_verify_scope` (`'full' == '<unset>'`), `test_steps_commands.py::test_bước_5_affected_*` ×3 (`'full: VERIFY_SCOPE=full' == 'affected: …'`), `test_5b_*` ×3, `test_coverage_gate_run.py::test_run_affected_thiếu_coverage_json_nhưng_0_test_thì_đạt`. Tác giả cả hai FIX chưa lần nào chạy bước 5 đủ (báo cáo FIX-072: "bước 5–8 chưa chạy"). | `tools/tests/test_steps_commands.py:48` (fixture `repo`), `tools/tests/test_run_sh.py:124` (`env = {**os.environ…}`), `tools/tests/test_coverage_gate_run.py:84` | `monkeypatch.delenv("VERIFY_SCOPE", raising=False)` trong fixture `repo` và các test `coverage_gate_run` dùng phạm vi mặc định; `_run_run_sh` bỏ `VERIFY_SCOPE` khỏi `env` trừ khi `extra_env` đặt. Chạy lại `verify --full` phải xanh. |
| 2 | P1 | LOG-02 (BE-00 §12 "không thu hẹp sai") | `affected()` chỉ thấy import tĩnh của `grimp`, bỏ sót phụ thuộc **nạp động** — mà app API sống bằng nạp động: `create_app` dò mọi `apps/api/<m>/router.py` qua `extensions.discover` (`importlib.import_module`) và nạp `apps.api.auth.verifier` bằng `importlib` ; fixture `api_client`/`auth_client`/`signed_in` được `conftest.py` nạp theo tên, test dùng không import. Bằng chứng: đổi `apps/api/auth/router.py` hay `verifier.py` → không chạy `apps/api/core/tests` (`test_routes.py` đối chiếu bộ route thật với BE-BIND, `test_common.py` tham số hoá case chung theo route của app thật, `test_app.py`), `apps/api/files/tests`, `apps/api/health/tests` — dù mọi test đó dựng app chứa router/verifier vừa đổi. Hệ quả: xanh giả (vd đổi `operationId`/path làm lệch BE-BIND) hoặc đỏ giả ở `case_gate` (case chung của route mới nằm trong `apps/api/core/tests` không chạy). | `tools/verify/affected.py:150-155` (`_classify`, chỉ cộng `graph`), `apps/api/core/app.py:57,89-96,105-106`, `packages/testing/fixtures/auth.py`, `api.py` | Thêm cạnh động tường minh: mọi đơn vị `apps/api/<m>` là phụ thuộc của `apps/api/core` theo chiều ngược (đổi `apps/api/*` → kéo mọi `apps/api/**/tests`), và đơn vị nào có `packages/testing` trong tập phụ thuộc ngược → kéo mọi thư mục test dùng fixture của file fixture đó (hoặc đơn giản: chạy đủ). Thêm test chốt: `affected(["apps/api/auth/router.py"]) ⊇ {"apps/api/core/tests","apps/api/files/tests"}`. |
| 3 | P1 | LOG-02 | `VERIFY_CHANGED` dựng bằng `git diff --name-only` có dò đổi tên (mặc định `diff.renames=true`) → file **chuyển đi** chỉ còn đường đích; đơn vị nguồn và mọi đơn vị import đường cũ không vào `affected`. Trước FIX-071 dòng này chỉ ảnh hưởng ngưỡng file bị chạm; nay nó thu hẹp cả tập test → xanh giả. Bằng chứng (repo tạm, `git mv packages/a/mod.py packages/b/mod.py`): `git diff --name-only` in `packages/b/mod.py`; `--no-renames` in cả `packages/a/mod.py`. | `tools/verify/run.sh:49` | `git diff --name-only --no-renames "$merge_base"`; thêm test `run.sh` với một lần `git mv`. |
| 4 | P3 | OPS / CON-05 | Volume tên cố định nhưng vẫn do compose quản lý: mọi lượt in `volume "appback-work" already exists but was created for project "appback-verify-concurrency-test-a"… Use external: true`; một `docker compose -p <project chủ> down -v` sẽ xoá volume của mọi worktree đang chạy. | `deploy/compose/verify.yml:46-47` | `external: true` + `docker volume create appback-work >/dev/null` trong `run.sh` (idempotent). |
| 5 | P3 | RES-03 | `gc`: `git worktree list … 2>/dev/null` hỏng → `VERIFY_VALID_NAMES` rỗng → `cmd_gc` xoá **mọi** `venv-*`/`mypy-*`; nay volume dùng chung nên xoá cả của worktree đang sống (chỉ là đệm, không mất dữ liệu). | `tools/verify/run.sh:173`, `tools/verify/steps.py:535` | Từ chối chạy khi danh sách rỗng. |
| 6 | P3 | LOG-01 | `testpaths` có `tests` gốc nhưng `_GRAPH_ROOTS` không có — khi thư mục này xuất hiện, test trong đó không bao giờ được kéo vào theo phụ thuộc (hôm nay chưa có thư mục, không tác động). | `tools/verify/affected.py:26`, `pyproject.toml:88` | Có `tests/` gốc → luôn thêm vào tập, hoặc đưa vào đồ thị. |

Đã soát, không thành finding: `_is_global` bắt đủ `conftest.py`/`pyproject.toml` mọi cấp/`uv.lock`/`.importlinter`/`packages/testing/**`/`tools/verify/**`/công cụ cổng/`docs/charter/**`/ảnh+compose verify; file không ánh xạ được → `None`; `integration` luôn `full`, `VERIFY_SCOPE` lạ → `ValueError`. `coverage_gate` ở `affected` giữ ngưỡng đơn vị + file bị chạm, `full` không đổi hành vi; thiếu `coverage.json` chỉ miễn khi `affected()==set()`. `case_gate` lọc fail-closed (op không ánh xạ được vẫn bị đòi). `copy_work.sh`: bước 7 đọc AppFront từ mount `/appfront` (bản chép `.cache/appfront` riêng) và `node_modules` từ `/work/contract-node` — không cần gì trong `.cache`/`.git` của `/src`; `chmod 644` vẫn chạy sau chép. Ảnh gắn tag theo băm `verify.Dockerfile`, Dockerfile không `COPY` gì từ context (ENTRYPOINT đọc `/src`) → không có ảnh cũ khi đổi. venv/mypy tách theo `VERIFY_NAME`, `contract-node` đổi tên nguyên tử. `# noqa: S603` đều có mã.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 4 | 0,60 |
| LOG | 15% | 1 | 0,15 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 4 | 0,40 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 1 | 0,07 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 5 | 0,15 |

Tổng: **3,82 / 5**

## PHÁN QUYẾT: REQUEST CHANGES

Ba P1 chưa waiver. Để được duyệt: (1) sửa độ cô lập `VERIFY_SCOPE` trong 3 file test — `run.sh verify --full`
trên đầu nhánh mới phải thoát 0 và in độ phủ; (2) `affected()` kéo đủ phụ thuộc nạp động của `apps/api`
(router/verifier qua `create_app`, fixture qua `conftest`) kèm test chốt; (3) `--no-renames` cho `VERIFY_CHANGED`
kèm test. P3 #4–#6 ghi `DEBT.md` hoặc sửa cùng lượt. FIX-072 (khởi động, ảnh theo băm, `gc` NO-101) tự nó đúng và
đo lại khớp; nếu cần gộp sớm có thể tách riêng sau khi sửa #1 phần `test_run_sh.py`.
