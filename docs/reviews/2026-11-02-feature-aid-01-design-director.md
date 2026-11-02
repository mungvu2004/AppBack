# Review merge feature/aid-01-design-director → main

- Ngày: 2026-11-02 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 03f9349c1a80 (gốc nhánh `ffcceeb0`; `main` = `4e1cd3b2`, chỉ thêm dữ liệu thư viện, `git merge-tree` sạch, không migration mới)
- Cổng: phạm vi **đầy đủ** (lượt 1, R-33b điều kiện 1; diff còn chạm migration, hợp đồng FE, `uv.lock`). Reviewer không tự chạy cổng đầy đủ; dùng các lượt `bash tools/verify/run.sh verify` của người điều phối:
  - lượt 1 @ aa64e199 (`_logs/aid-01-verify-1.log`): **mã thoát 1** — bước 5 hỏng `deploy/tests/test_env_example.py::test_env_example_no_value_looks_like_a_real_secret` (`DESIGN_DIRECTOR_PROFILES_PATH=packages/domain/library/profiles.jsonl` trông như bí mật). Sửa ở 037b7823.
  - lượt 2 @ 037b7823 (`_logs/aid-01-verify-2.log`): **mã thoát 1** — 9721 passed nhưng `coverage_gate` hỏng: `tools/design_director` thiếu `__init__.py`. Sửa ở 03f9349c.
  - lượt 3 @ 03f9349c (`_logs/aid-01-verify-3.log`): **mã thoát 1** — 9721 passed + 1 ERROR teardown `apps/api/admin_ml_datasets/tests/test_contract.py::test_ml_create_dataset__C07` (Redis f14 hết giờ kết nối; module không thuộc diff).
  - lượt 4 @ 03f9349c (`_logs/aid-01-verify.log`, log cổng `.cache/src-out/verify/20261102T105225Z-03f9349c1a80.log`): **mã thoát 1** — 9720 passed, 1 failed `apps/ml/walls/tests/test_tasks.py::test_segment_walls__J01` (lỗi `redis`, module không thuộc diff).
  - Bước 3 (mypy), 5b, 6 (migrate_check), 7 (H1–H5), 8 (openapi) **chưa chạy** ở cả 4 lượt. Lượt 3 và 4 hỏng vì Redis dùng chung của f14 (PERF-10), hai lần liền ở hai test khác nhau. Lượt sau nên chạy `VERIFY_SHARED_STACK=off`, hoặc tạo lại Redis f14 trước.
- Độ phủ (lượt 2, @ 037b7823, chỉ khác HEAD ở `__init__.py` một dòng): tổng dòng 99,32 % · nhánh 97,51 % | `apps/api/design_director` 97,98/96,67 · `apps/worker/design_director` 97,44/97,78 · `apps/worker/pipeline_quality` 99,48/96,15 · `packages/genai` 100/100 · `packages/domain` 99,78/98,70 · `packages/db` 97,58/95,90 · `packages/core` 100/100 · `packages/messaging` 100/100 · `packages/testing` 99,46/98,40 · `tools` 98,76/96,52 · tập file bị chạm 98,74/98,28. Lượt đích của reviewer (`run.sh shell`, pytest các thư mục mới): `apps/worker/design_director/tasks.py` 87 % dòng (thấp nhất), còn lại ≥ 96 %.
- Đối chiếu riêng (reviewer, `run.sh shell` sau cổng): `python -m apps.api.core.openapi --out /tmp/o.json --compare docs/contracts/openapi.json` → **thoát 1** ("docs/contracts/openapi.json lệch với bản vừa xuất").

## Phạm vi và điều kiện dừng sớm

- Cây sạch. 6 commit: `1b676443 feat`, `89ff2498 feat`, `f31a6b2c chore(contract)`, `aa64e199 docs(charter)`, `037b7823 fix(deploy)`, `03f9349c chore(tools)`; đều đúng mẫu và có `Prompt: AID-01`. Có `changes/AID-01.md`.
- 69 file, ~+6890/−9; bỏ `materials.json`/ảnh/test thì ~2000 dòng logic — vượt 400 (P2 MNT-05 về hình thức). Không tách: các lớp genai → domain → api → worker phụ thuộc thẳng nhau, tách chỉ tạo nhánh dở.
- Không `pragma: no cover/branch`, không `# type: ignore` trần (mọi cái có mã), không `# noqa` trần, không skip/xfail mới, không hạ ngưỡng.
- `docs/charter/*`: chỉ commit aa64e199 chạm, chỉ chạm tài liệu (`changes/AID-01.md` + 3 tệp charter), có trailer `Charter-Approved: changes/AID-01.md (người dùng duyệt 2026-11-02)`; dòng duyệt có thật ở `changes/AID-01.md:14` ("oke"). Đạt ngoại lệ.
- `uv.lock`: +54 dòng, chỉ `appback-genai`, `google-auth`, `pyasn1`, `pyasn1-modules`, `rsa`, `cachetools` và cạnh `apps/worker → appback-genai` — đúng hệ quả của `packages/genai/pyproject.toml` + `apps/worker/pyproject.toml` (urllib3 đã có trong lock). Đạt.
- `tools/contract/APPFRONT_SHA` = 81842f1a, do người điều phối ghim (tiền lệ LB-01, LIB-FILES). Xem finding 2.
- Migration `r20261102_aid_01` nối sau `r20261028_ux_r2` (head hiện tại của chuỗi); quét `down_revision` cho ra đúng 1 head.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P1 | API (hợp đồng) / CI | Nhánh thêm N47/N48 + 3 schema nhưng không sinh lại `docs/contracts/openapi.json` (0 lần xuất hiện `design-concept`). CI `job_typecheck` luôn chạy bước 8 ở chế độ so sánh (`VERIFY_BRANCH=integration`) → PR và `main` sẽ đỏ. Reviewer đã chạy `--compare`: thoát 1. Cổng local không bắt vì bước 8 ở nhánh worker chỉ xuất | `tools/ci/job.sh:196-201`; `tools/verify/steps.py:439-442`; `docs/contracts/openapi.json` | Người điều phối: `bash tools/verify/run.sh openapi`, chép vào `docs/contracts/openapi.json`, commit `chore(contract): regenerate openapi.json for N47 N48` |
| 2 | P1 | API (hợp đồng FE) | `APPFRONT_SHA` = 81842f1a chỉ có ở nhánh **local** `feature/aid-01-design-director` của AppFront: không remote nào chứa (`git branch -r --contains` rỗng), thiếu 3 commit của `origin/master`. Vào `main` lúc này thì CI không lấy được commit, và `main` ghim FE chưa merge; nếu FE squash thì SHA mồ côi | `tools/contract/APPFRONT_SHA:1` | Thứ tự merge: (a) gộp `origin/master` vào nhánh FE, merge FE vào `master`, push; (b) ghim lại `APPFRONT_SHA` = commit trên `origin/master` có `src/api/schemas/designConcept.ts`; (c) chạy lại `run.sh verify --steps 5,7` (bước 7 cần junit bước 5); (d) commit `chore(contract)`; rồi mới merge BE |
| 3 | P2 | RES (timeout/trần) | Charter ghi "trần một lượt 15 phút" và lịch quét chốt `running` > 15 phút thành `DESIGN_DIRECTOR_STALLED`, nhưng mã không có trần tổng. Một lời gọi Vertex xấu nhất 4 × 120 s + 2+4+8 s ≈ 8,2 phút, một lượt tối đa 4 lời gọi (chọn kiểu, concept, thử lại, bổ sung) ≈ 33 phút; trần Celery chung 3300 s. Khi lượt quá 15 phút: lịch quét đánh `failed`, worker vẫn chạy và trả tiền Gemini, `finish` (lọc `status='running'`) thành no-op, kết quả mất | `packages/genai/vertex.py:35-36,163-180`; `apps/worker/design_director/run.py:212-243`; `apps/api/design_director/settings.py:24`; `docs/charter/BE-00.md:327` | Thêm hạn chót tổng cho lượt (vd. 12 phút) trong `_Caller`: trước mỗi lời gọi kiểm thời gian còn lại, truyền `min(TIMEOUT_S, còn lại)` xuống `post`; hết giờ → `DESIGN_DIRECTOR_FAILED`. Test bằng `FakeGenAI` + đồng hồ giả |
| 4 | P3 | CON (hạn mức) | Đếm hạn mức rồi mới chèn, hai câu tách rời: hai N48 song song của cùng chủ với hai kiểu khác nhau (hoặc N48 + `enqueue_auto`) vượt trần vài lượt. Dự án nhiều tầng: mỗi tầng xong pipeline lại xếp một lượt tự chọn với khoá mới, nên một lần tải N tầng tốn N lượt Gemini và N phần hạn mức, chỉ lượt cuối có ích | `apps/api/design_director/service.py:321-332`; `apps/api/design_director/state.py:612-624`; `apps/worker/pipeline_quality/service.py:199` | `pg_advisory_xact_lock(hashtext(owner))` quanh đếm + chèn. Trong `enqueue_auto`: đã có lượt tự chọn `queued` của dự án → cập nhật khoá của nó thay vì chèn lượt mới (hoặc chốt `failed` lượt cũ còn `queued`) |
| 5 | P3 | PERF | `load_inputs` tải tuần tự ảnh xem trước của **mọi** mẫu đã publish có hồ sơ, trong khi bảng ảnh chỉ dùng ứng viên đã xếp hạng (≤ 12 món chính, ≤ 4 món phụ mỗi vai trò). Thư viện nay đã ~900 mẫu → hàng trăm lần đọc kho và vài chục MB RAM mỗi lượt khi có `profiles.jsonl` | `apps/worker/design_director/tasks.py:394-395` | Xếp hạng trước (cần kiểu đã chọn) rồi chỉ tải ảnh của `cards`; hoặc truyền loader ảnh lười vào `run_concept` |
| 6 | P3 | OPS | Đường mặc định `packages/domain/library/profiles.jsonl` không có trong repo, và repo không nói tệp sinh ở đâu hay đưa vào ảnh worker thế nào → khi bật, AI chỉ chọn sơn/sàn, `models` luôn rỗng, `additions` không có `modelId`. `changes/AID-01.md` không ghi nợ này | `apps/worker/design_director/tasks.py:320`; `deploy/compose/env.example` | Ghi dòng nợ trong `changes/AID-01.md` (nguồn tệp, người sinh, cách đưa vào ảnh/volume) hoặc commit tệp |
| 7 | P3 | R-27 (ranh giới sở hữu) | Nhánh sửa `.importlinter` (CLAUDE.md: chỉ B0-01; mọi commit trước đều `Prompt: B0-01`) và `apps/worker/pipeline_quality/service.py` (module của prompt khác). Nội dung hợp lý: siết hợp đồng cho `packages.genai`; hook bọc `try/except` và có 2 test | `.importlinter:23,48,187`; `apps/worker/pipeline_quality/service.py:147-160,199` | Người điều phối ghi chấp nhận trong `changes/AID-01.md` ("Lệch khỏi prompt"), hoặc tách `.importlinter` thành commit `chore(repo)` `Prompt: B0-01` |
| 8 | P3 | R-10 / MNT | `_versions()` nhập `packages.domain.design_director.prompts` bằng `importlib` và lùi về `"0"` khi `ModuleNotFoundError`: phần dự phòng còn sót từ lúc các agent làm song song. Gói đã có trong nhánh, nên nhánh này là mã chết (không test chạm) và còn giấu cạnh import khỏi import-linter | `apps/api/design_director/state.py:127-134` | `from packages.domain.design_director.prompts import MATERIALS_VERSION, PROMPT_VERSION` rồi bỏ `_versions` |
| 9 | P3 | OBS / chất lượng đầu vào AI | `load_font` ghi "DejaVu trong ảnh Debian", nhưng `worker.Dockerfile` không cài `fonts-dejavu-core` → ảnh thật dùng phông mặc định của Pillow; chữ như "ấm" trên bảng ứng viên/sơ đồ ra ô thiếu glyph | `apps/worker/design_director/fill.py:291-298`; `deploy/docker/worker.Dockerfile:105-107` | Cài `fonts-dejavu-core` ở tầng runtime lần dựng ảnh sau, hoặc để chú thích bảng thuần ASCII |
| 10 | P3 | TEST | `tools/design_director/build_materials.py` (160 dòng sinh dữ liệu đã commit) không có test; giờ đã có `__init__.py` nên bị đo, kéo độ phủ `tools` xuống | `tools/design_director/build_materials.py` | Test nhỏ cho `srgb_to_lab`/`describe` và luật chia tập (`DRY_PATTERN_MAX`), hoặc đưa tool ra ngoài repo |
| 11 | P3 | DOC (charter) | BE-00 §13.1 chưa có dòng `packages/genai` (google-auth, urllib3; cạnh core) và cạnh `apps/worker → genai` | `docs/charter/BE-00.md:509-525` | Thêm vào bản charter kế tiếp (người dùng duyệt câu chữ) |
| 12 | Nit | LOG | `summaryVi` từ Gemini không giới hạn độ dài (`nameVi` có giới hạn 40) | `packages/domain/design_director/answer.py:68` | Cắt ở ~600 ký tự |
| 13 | Nit | LOG (prompt) | Prompt bổ sung đồ mô tả khoá `side`, nhưng `edge_summary` không trả khoá này (trả `usage`); docstring `fill_prompt` cũng vậy | `packages/domain/design_director/prompts.py:134`; `apps/worker/design_director/fill.py:169-181` | Sửa câu prompt (kèm tăng `PROMPT_VERSION`) |
| 14 | Nit | R-01 | Hàm lồng `to_px` không có docstring | `apps/worker/design_director/fill.py:310` | Thêm một dòng |
| 15 | Nit | MNT-05 | ~2000 dòng logic (> 400); commit 1b676443 đổi `test_charter` lên 50 dòng N trước commit charter aa64e199, nên các commit giữa chừng đỏ | — | Squash khi merge là đủ |

Đã soát và không thấy vấn đề:
- **SEC.** N47 đòi thành viên, N48 đòi `project.settings.edit`, người ngoài 404 (`require_project`). Thân N48 là `Literal` 12 mã. Khoá SA là `SecretStr`; lỗi JSON của khoá ném `from None`; log chỉ ghi `exc.code`, không ghi thân HTTP. Gemini không thấy id/tên mẫu, đầu ra bị ép bằng enum. `usage` không ra dây.
- **CON.** `ON CONFLICT … WHERE status IN ('queued','running')` khớp chỉ mục unique một phần; bên thua đọc lại bên thắng (test C14). Mọi `UPDATE` lọc trạng thái nguồn nên giao lặp là no-op (J06). Task gửi qua `on_after_commit` (K17). Lịch quét `FOR UPDATE SKIP LOCKED`. Session đóng trước khi gọi AI hoặc chạm kho (K22).
- **DB.** Chỉ thêm bảng mới (expand). CHECK trạng thái và CHECK kiểu khớp giữa model và migration. FK `ON DELETE CASCADE`.
- **API/FE.** Đã đối chiếu với `src/api/schemas/designConcept.ts` @ 81842f1a: `kind`/`variant` của `ADD` nằm trong `FURNITURE_KINDS`/`FURNITURE_VARIANTS`; vai trò `ROLE_TYPE` trùng `DESIGN_MODEL_ROLES`; ref vật liệu `library:…` khớp `materialRefSchema`; các refine `endedAt`/`failureCode`/`result` khớp luật chuyển trạng thái.
- **TEST.** SQL/khoá/after-commit/lịch quét chạy trên Postgres + Redis thật; chỉ cổng Vertex là giả (`FakeGenAI`, `post`/`sleep` tiêm được; có thêm một server HTTP cục bộ cho `urllib_post`).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 4 | 0,60 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 4 | 0,40 |
| RES | 10% | 3,5 | 0,35 |
| DB/API | 10% | 3 | 0,30 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 3,5 | 0,175 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,19 / 5

## PHÁN QUYẾT: REQUEST CHANGES

Mã nghiệp vụ tốt: ranh giới sạch, có idempotency/khoá, test dùng dịch vụ thật, độ phủ cao. Nhưng còn hai P1 chưa có waiver. Cả hai là việc của người điều phối khi merge, không phải sửa mã. Ngoài ra cổng đầy đủ chưa có lượt thoát 0. Để được duyệt:
1. **Finding 1:** sinh lại `docs/contracts/openapi.json` và commit `chore(contract)`.
2. **Finding 2:** merge FE AID-01 vào `master` của AppFront trước và push; ghim lại `APPFRONT_SHA` vào commit trên `origin/master`; chạy lại `--steps 5,7`.
3. Một lượt `bash tools/verify/run.sh verify` đầy đủ **thoát 0** trên HEAD cuối, gồm cả bước 3, 5b, 6, 7, 8.
4. **Finding 3 (P2):** sửa ngay (hạn chót tổng ≤ trần 15 phút của charter), hoặc ghi dòng nợ trong `changes/AID-01.md`.
5. **Finding 4–11 (P3):** ghi dòng nợ trong `changes/AID-01.md`, hoặc sửa ở lát sau.

Lượt review 2 chỉ cần soát diff vòng sửa (phạm vi đích), cộng bằng chứng của cổng đầy đủ ở mục 3.
