# Review merge feature/lb-01-lighting-bake → main

- Ngày: 2026-11-01 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 0d9626f98aa7 (sau `origin/main` 3 commit: nhánh **chưa** có PERF-11 `f14f478c`)
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 1, lượt 1). `bash tools/verify/run.sh verify` chạy từ worktree tại 0d9626f98aa7: **mã thoát 1**, 10 phút 56 giây (log `F:/runs/lighting-bake/review-full.log`; log cổng `.cache/src-out/verify/20261101T101821Z-0d9626f98aa7.log`, SHA khớp HEAD). Bước 0, 1, 2, 4 đạt; bước 5 **hỏng** (pytest 9396 passed trong 9 phút 23 giây, `coverage_gate` hỏng); bước 3, 5b, 6, 7, 8 **chưa chạy**. Trước khi chạy: C: còn 99,9 GB, không có container verify khác, không có `web-ctx-*`, `f14-ml-1` dừng trong lúc chạy rồi bật lại. Worktree không có `tools/verify/gate_lock.sh` nên lượt này không vào hàng ở khoá cổng.
- Độ phủ: tổng dòng 99,37 % · nhánh 97,51 % | `apps/worker/lighting_bake` 93,40 % / **85,29 %** (< 90 %) · `apps/api/lighting_bake` 98,45 / 100 · `apps/api/core` 99,92 / 99,67 · `packages/core` 100 / 100 · `packages/db` 97,52 / 95,90 · `packages/messaging` 100 / 100 · `packages/storage` 99,68 / 98,61 · `packages/testing` 99,44 / 98,37 · `tools` 98,76 / 96,52 | tập file bị chạm 98,40 / 96,88.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước (`2026-11-01-feat-walls-arc.md`).

## Phạm vi và điều kiện dừng sớm

- Cây sạch. Một commit `4b99d9fc feat(lighting-bake): …` (`Prompt: LB-01`, dòng đầu đúng mẫu) và một merge `origin/main` (merge của git, giải xung đột `APPFRONT_SHA`). 57 file, +2421/−22. Nhánh chưa lên `origin` (dự kiến: chưa duyệt). Có `changes/LB-01.md`.
- Không `pragma`, `type: ignore`, `noqa` trần, skip/xfail mới, không hạ ngưỡng; không chạm `uv.lock`, `pyproject.toml`, `openapi.json`, `tools/verify/*`.
- **Dừng sớm §2, không đạt:** `4b99d9fc` sửa `docs/charter/BE-00.md` (W4 `bak_`, §7 hàng `bake`, §8 khoá, §11 trần thân N42, §12 miễn H1 cho N44), `docs/charter/BE-BIND.md` (N42–N44) và `docs/charter/HOP-DONG-MOI.md` (§11) **cùng** `.py`, `tools/**`, `deploy/**`, và **không** có trailer `Charter-Approved:`. Không tìm thấy bản duyệt nào của người dùng (thân commit, `changes/LB-01.md`, `F:/runs/lighting-bake/*` đều không có). Tiền lệ: `2026-10-27-fix-apt-title-block.md` (REJECT cùng lý do).
- `tools/contract/APPFRONT_SHA` = fb24d824: tệp cấm ở §2, **chấp nhận** vì phiên tác giả là điều phối của LB-01 (`F:/runs/lighting-bake/CONTRACT.md:56-57`), fb24d824 đã ở `origin/master` của AppFront và là hậu duệ của 7d5368d5 (ghim hiện tại của `main`). Tiền lệ `2026-10-27-fix-apt-title-block.md`. Nên tách thành commit `chore(contract): …` riêng khi viết lại lịch sử (Nit 12).
- `tools/contract/check.py:47` (thêm `lighting_bake_download_file` vào `H1_EXEMPT`, docstring ghi "thêm tên vào đây là trái hiến chương") và `tools/case_gate.py:34` (`INFRA_OPS`) chỉ hợp lệ khi dòng §12 của BE-00 được duyệt: đi cùng finding A.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| A | **§2 REJECT** | BE-00 §2 / merge-review §2 | Commit sửa `docs/charter/*` cùng mã, không có `Charter-Approved:` trỏ tới bản duyệt thật. Kéo theo miễn H1 mới trong `check.py`/`case_gate.py` chưa có căn cứ | `4b99d9fc`; `docs/charter/BE-00.md`, `BE-BIND.md`, `HOP-DONG-MOI.md`; `tools/contract/check.py:47`; `tools/case_gate.py:34` | Đưa câu chữ charter (W4, §7, §8, §11, §12 H1 N44, BE-BIND N42–N44, HOP-DONG-MOI §11) cho người dùng duyệt. Nhánh chưa lên `origin`, viết lại được: tách `4b99d9fc` thành (1) `docs(charter): LB-01 …` **chỉ** ba tệp charter, trailer `Charter-Approved: người dùng duyệt <ngày> ("<câu duyệt>")` hoặc đường tệp duyệt; (2) `feat(lighting-bake): …` phần mã; (3) `chore(contract): pin AppFront fb24d824`. Cây cuối không đổi |
| B | P1 | TEST / BE-00 §12 bước 5 | Cổng đầy đủ mã thoát 1: `coverage_gate` hỏng, `apps/worker/lighting_bake` nhánh 85,29 % < 90 %. Bước 3 (mypy), 5b, 6, 7, 8 chưa chạy nên chưa có bằng chứng cho migration, hợp đồng H1–H5 và openapi. Không đo được từng tệp vì cổng `feat/editor3d-dot2` chạy ngay sau (luật RAM). Nhánh chưa test, đọc từ mã: `_run_blender` `LockLost` → `DEPENDENCY_UNAVAILABLE`; `finish` trả `False` (`lighting_bake_finish_skipped`, xoá tiền tố); `_validate`: tệp vượt trần, magic sai, manifest > 64 KiB, JSON hỏng, JSON không phải object; `fail_lighting_bake` khi `project_id is None`; `_spawn` nhánh `BaseException` (huỷ giữa chừng — J05 thay hẳn `_run_blender` nên không đi qua) | `apps/worker/lighting_bake/tasks.py:118-192` (`_spawn`, `_run_blender`, `_validate`), `:244-256`, `:259-274` | Thêm chế độ cho `tests/fake_blender.py` (`bad-magic`, `bad-manifest`, `big`) và test cho `LockLost`, finish bị lịch quét chốt trước, dự án đã xoá. Chạy `run.sh verify --fast` rồi cổng đầy đủ, dán mã thoát |
| 1 | P2 | MNT-05 | ~1250 dòng ngoài test (api 420, worker 553 gồm `.bpy` 183, deploy 131, packages 150) > 400. Một lát dọc, các phần phụ thuộc nhau: tách bây giờ không đáng, chấp nhận | toàn nhánh | Không cần làm; lát sau chia api / worker / deploy |
| 2 | P3 | RES / OPS | Lịch quét chốt `LIGHTING_BAKE_STALLED` chỉ trong DB, không xoá object: `input.glb` (tới 128 MiB) và đầu ra dở nằm lại tới lần nướng **thành công** sau của cùng dự án (`_older_bakes`); không có lần sau thì nằm mãi | `apps/api/lighting_bake/jobs.py:34-38`, `:62-87` | `RETURNING id, project_id`, sau commit gọi `storage.delete_prefix(lighting_bake_prefix(p, id))` cho từng lượt bị chốt (như `fail_lighting_bake`) |
| 3 | P3 | LOG / CON | `claim` giữ `started_at` của lần nhận đầu (`COALESCE`), lịch quét chốt `running` sau 70 phút, còn một lượt Blender được 50 phút (`DEFAULT_TIMEOUT_S` 3000). Lượt bị OOM (`-SIGKILL` → `DEPENDENCY_UNAVAILABLE`, thử lại) sau hơn ~20 phút sẽ bị lịch quét chốt giữa lần thử lại; `finish` trả `False`, kết quả bỏ đi, GPU chạy phí | `apps/api/lighting_bake/state.py:24`; `apps/api/lighting_bake/settings.py:24`; `apps/worker/lighting_bake/settings.py:14`; `apps/worker/lighting_bake/tasks.py:151-152` | Mỗi lần `claim` đặt `started_at = :now` (worker chết thì không có lần nhận mới, lịch quét vẫn bắt được), hoặc đặt trần `running` ≥ timeout + biên **mỗi lần thử**; thêm test cho ca này |
| 4 | P3 | RES | OOM của một GLB nặng là lỗi tất định nhưng bị coi là tạm: thử lại đủ `len(backoff)` lần, mỗi lần tới 50 phút trên GPU dùng chung | `apps/worker/lighting_bake/tasks.py:151-152` | Chặn trước theo kích thước/số tam giác của đầu vào, hoặc OOM lần hai trên cùng lượt → `PermanentError(LIGHTING_BAKE_FAILED)` |
| 5 | P3 | SEC (phòng thủ nhiều lớp) | Blender đọc GLB người dùng tải lên (gồm ảnh nhúng, qua bộ giải mã C của Blender) trong container mang đủ env ứng dụng (DSN, khoá S3; `environment: *app-env`). Env của con đã lọc, nhưng con cùng uid 10001 đọc được `/proc/<pid celery>/environ`. Docstring "Blender chỉ thấy thư mục tạm" nói quá | `apps/worker/lighting_bake/tasks.py:66-68`; `deploy/compose/base.yml:291-300` (`:298`) | Sửa docstring cho đúng; ghi nợ: chạy Blender dưới uid riêng (`setpriv`) hoặc tách bước Blender khỏi tiến trình giữ bí mật |
| 6 | P3 | OPS / thiếu bằng chứng | Đường CPU (khoá `gpu:0` bận, vd. đang huấn luyện) chưa đo: commit chỉ ghi GPU 19 phút trên RTX 4050. CPU `-t 4`, 2048², 128 mẫu nhiều khả năng vượt trần 50 phút, tức mọi lượt nướng lúc GPU bận sẽ thành `LIGHTING_BAKE_TIMEOUT` sau 50 phút CPU | `apps/worker/lighting_bake/tasks.py:156-170`; `apps/worker/lighting_bake/blender.py:11` | Đo một lượt CPU trên căn mẫu, ghi vào `changes/LB-01.md`; nếu > 50 phút: chờ GPU (xếp lại hàng) thay vì chạy CPU, hoặc hạ mẫu/kích thước khi chạy CPU |
| 7 | P3 | OPS | `bake` `mem_limit: 8g` trong khi WSL máy dev giới hạn 10 GB (chống BSOD 0x113); chạy cùng phần còn lại của f14 (ml ~2,5 GB) dễ cạn RAM. Dịch vụ sau profile `bake` nên mặc định tắt | `deploy/compose/base.yml:297` | Ghi vào `changes/LB-01.md`/SETUP: bật profile `bake` thì dừng `f14-ml-1` và không chạy cổng song song |
| 8 | P3 | TEST-01 / SEC | N44 lọc `project_id` đúng (`_DONE`), nhưng không có test chống IDOR: thành viên dự án B lấy tệp của lượt thuộc dự án A qua đường của B → 404. N42 không có test thân > 128 MiB → 413 | `apps/api/lighting_bake/service.py:50`, `:103-123`; `apps/api/lighting_bake/tests/test_routes.py:240` | Thêm hai test đi qua dịch vụ thật |
| 9 | Nit | LOG | `except IntegrityError` → 409 `LIGHTING_BAKE_IN_PROGRESS` cả khi lỗi là FK (dự án bị xoá trong lúc tải 128 MiB) | `apps/api/lighting_bake/service.py:85-88` | Phân biệt theo tên ràng buộc (`uq_lighting_bakes_active`), FK → 404 `project` |
| 10 | Nit | MNT | `bake_glb.bpy:3` ghi `bake_glb.py`, mặc định `samples=512` trong khi worker gửi 128; `:182` `open(...)` không đóng | `apps/worker/lighting_bake/bake_glb.bpy:3`, `:182` | Sửa chú thích; `with open(...)` |
| 11 | Nit | R-07 | `GPU_LOCK_NAME = "gpu:0"` khai lại (ranh giới import chặn `apps.ml`) | `apps/worker/lighting_bake/tasks.py:61`; `apps/ml/runtime/gpu.py:25` | Đưa hằng về `packages.messaging` cho hai bên cùng nhập |
| 12 | Nit | OPS | Ghim `APPFRONT_SHA` nằm trong commit `feat` | `tools/contract/APPFRONT_SHA` | Tách khi làm finding A |

Đã soát, không có finding: SEC biên vào (magic bytes GLB, `require_project` `layer.edit`/thành viên, 404 trước 403, tên tệp N44 theo danh sách trắng, id `bak_` kiểm mẫu trước DB, `Content-Disposition` attachment, `Cache-Control: private`); CON (chỉ mục duy nhất một phần + test C14 song song trên Postgres thật, `UPDATE … WHERE status` làm chuyển trạng thái idempotent, gửi task sau commit, `FOR UPDATE SKIP LOCKED` ở lịch quét); PERF (thân N42 đọc theo luồng, `rollback` trả kết nối trước khi nhận thân, tải/ghi tệp theo khúc trong luồng phụ, `LIMIT` ở truy vấn); DB (migration chỉ mở rộng, CASCADE theo dự án, tên CHECK theo quy ước; bước 6 chưa chạy nên chưa kiểm được một head); deploy (Blender ghim phiên bản + SHA-256, tầng tải tách khỏi mã, target mặc định vẫn là `worker`, nginx 128m + `proxy_request_buffering off`).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 4,5 | 1,125 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 4 | 0,40 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 3,5 | 0,245 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,39 / 5

## PHÁN QUYẾT: REJECT

Dừng sớm theo §2: commit sửa `docs/charter/*` cùng mã mà không có `Charter-Approved:` trỏ tới bản duyệt thật (A). Riêng cổng đầy đủ cũng đỏ (B: nhánh `apps/worker/lighting_bake` 85,29 %, bước 3/5b/6/7/8 chưa chạy), nên kể cả khi qua A vẫn là REQUEST CHANGES. Phần mã không có P0; thiết kế trạng thái, đồng thời và biên vào chắc chắn.

Để được duyệt ở lượt sau:
1. Người dùng duyệt câu chữ charter của LB-01. Tách `4b99d9fc` thành commit charter chỉ tài liệu, mang `Charter-Approved: …`, commit mã và commit ghim `APPFRONT_SHA` (A, Nit 12).
2. Nâng độ phủ nhánh `apps/worker/lighting_bake` ≥ 90 % bằng các test nêu ở B; gộp `origin/main` mới (PERF-11, `gate_lock.sh`) rồi chạy `bash tools/verify/run.sh verify` đầy đủ, mã thoát 0 cả 8 bước (lượt 2 chạm điều kiện "đầy đủ" vì có mã và charter mới).
3. Nên làm cùng lượt (không chặn): finding 2, 3, 8; ghi 4–7 làm nợ trong `changes/LB-01.md` (repo không còn `DEBT.md`).
4. Sau khi merge, người điều phối chạy `run.sh openapi` và cập nhật `docs/contracts/openapi.json` (N42–N44).
