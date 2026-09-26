# Review merge `docs/test-scope-rule` → main

- Ngày: 2026-09-27 · Reviewer: phiên /merge-review (độc lập, R-37) · Commit đầu nhánh: `4363f332885a`
- Phạm vi kiểm: **đích** — diff chỉ 3 file Markdown (`RULE-CODE.md`, `CLAUDE.md`,
  `.claude/skills/merge-review/SKILL.md`), không mã Python, không cấu hình công cụ, không migration,
  không dây/hợp đồng; ngoài "lượt đầu" thì không điều kiện nào (2)–(6) của chính R-33b bị chạm, nên
  bằng chứng cổng cần thiết là bước lint trên cây đầy đủ.
- Cổng: phạm vi đích; `bash tools/verify/run.sh verify --steps 1,2` mã thoát **0**
  (bước 1 `ruff format --check` đạt — 756 file; bước 2 `ruff check` đạt; log: `r33b-verify12`, pane RUNNER).
  Bước 3–8 **chưa chạy** (không có `.py` nào đổi — E.10: không báo "đạt" cho bước chưa chạy).
- Độ phủ: không đo (phạm vi đích, diff không chứa file mã) — không có file mã nào đổi để đo.

## Kiểm sơ bộ (điều kiện dừng sớm §2 — không điều kiện nào bật)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` trong worktree tại `4363f33` | rỗng |
| Số commit vào `main` | 1 (`docs(repo): assess test scope before each gate run (R-33b)`) |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt |
| Trailer `Prompt:` | `git log -1 --format='%(trailers:key=Prompt,valueonly)'` in `dieu-phoi` (R-36b đạt: khối trailer liền nhau, có dòng trống trước) |
| File cấm (`docs/charter/*`, `openapi.json`, `uv.lock`, `APPFRONT_SHA`, `DEBT.md`) | 0 file bị chạm |
| `pragma`, `noqa` trần, `type: ignore`, `skip`/`xfail` mới, hạ ngưỡng | 0 |
| `changes/dieu-phoi.md` | không yêu cầu — `dieu-phoi` không phải prompt spec có bước cổng điều kiện; tiền lệ cùng trailer (`7d2b01e`, `1478543`) cũng không có file này |
| Bảng Markdown | nguyên vẹn: hàng R-33b đúng 2 ô (dấu gạch dọc trong ô đã escape), hàng `verify` của `CLAUDE.md` 4 pipe như mọi hàng khác |
| Số đo được dẫn | khớp: 1.205 s ≈ 20,1 phút cho 4.729 test (`docs/reviews/2026-09-26-feature-b2-05b-quality-api.md`) |
| Mâu thuẫn hiến chương | `BE-00 §12` không có câu bắt buộc chạy cả 8 bước mỗi lượt, và §12 đã có cơ chế phạm vi (`VERIFY_TOUCHED`, `VERIFY_BRANCH`) — R-33b **không** trái hiến chương. Một tồn tại: `docs/charter/FIX.md` [7] (xem P3-5) |

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| P2-1 | P2 | R-33b, TEST-05 | Lượt **đích** (`--steps 1,2,3,4`) không bao giờ chạy `coverage_gate.py`, mà cổng này còn một loạt kiểm **tĩnh** không cần coverage và tốn vài giây: `pragma: no cover`/`no branch`, `# mypy: ignore-errors`, `@no_type_check`, `conftest.py` lồng, `.coveragerc`/`pytest.ini`/`ruff.toml`…, bảng lạ ở `pyproject.toml` thành viên, `--cov` trong `addopts`, `test_*.py` ngoài `tests/`, thư mục có `.py` thiếu `__init__.py` (`tools/coverage_gate.py:85`–`190`). Vòng sửa thêm thư mục/file mới hay một `pragma` thì **đỏ trên `main`** mà lượt đích không thấy | `RULE-CODE.md:68` | Thêm điều kiện đầy đủ **(7): thêm/xoá file hoặc thư mục `.py`, thêm file test, hoặc sửa `pyproject.toml` thành viên** — chỉ bước 5 mới chạy `coverage_gate` (pragma, `conftest.py` lồng, thiếu `__init__.py`, `test_*.py` ngoài `tests/`) |
| P2-2 | P2 | R-33b, DB-03 | Điều kiện (2) **loại trừ** `packages/db/models/<module mình>.py`, và (3) chỉ bật khi *migration* đổi; nhưng bước 6 so **model ↔ DB** và **tên CHECK ↔ model** (BE-00 §12 bước 6). Sửa model của chính mình mà chưa viết migration → bước 6 đỏ, lượt đích mù hoàn toàn — đúng loại lệch mà bước 6 tồn tại để bắt | `RULE-CODE.md:68` | (3) → "thêm/sửa migration **hoặc model SQLAlchemy** (bước 6 so model với DB và tên CHECK)" |
| P2-3 | P2 | R-33b, TEST-02 | Lượt đích đổi **tập test được thu**, trong khi repo đang có nợ phụ thuộc thứ tự chạy: `NO-211` — `apps/api/auth_recovery/tests/test_e2e.py` xanh trong cổng đầy đủ nhưng **hỏng khi chạy lẻ** (`Received unregistered task …`; task chỉ được đăng ký khi một test khác nhập module). Hệ quả hai chiều: đỏ ở lượt đích có thể là báo động giả, và xanh ở lượt đích có thể che một lượt đầy đủ đỏ | `RULE-CODE.md:68` | Thêm một câu: "Đỏ ở lượt đích phải xác nhận lại ở phạm vi **đầy đủ** trước khi coi là lỗi thật; module có nợ phụ thuộc thứ tự chạy đang mở trong `DEBT.md` (vd `NO-211`) luôn chạy đầy đủ." |
| P2-4 | P2 | R-33b, MNT-02 | Điều kiện (2) chỉ kể **4 trong 10** gói `packages/*`. Đọc đúng chữ thì `packages/domain` (28 file nhập), `packages/ml_contracts` (14), `packages/observability` (11), `packages/mail` (4), `packages/vision` (2) rơi về **đích** dù đều là mã dùng chung; `apps/worker/celery_main.py`, `apps/ml/celery_main.py`, `apps/ml/runtime/**` (điểm vào dùng chung) cũng không có trong danh sách. Danh sách kiểu kể tên sẽ lệch mỗi lần thêm gói | `RULE-CODE.md:68` | Đổi sang danh sách **loại trừ**: "chạm `packages/**` (trừ `packages/db/models/<module mình>.py` và `tests/` của module mình), `apps/api/core/**`, `apps/{worker,ml}/celery_main.py`, `apps/ml/runtime/**`, `conftest.py`, …" |
| P2-5 | P2 | OBS-04, K25 | Mẫu phán quyết sửa dòng "Cổng:" nhưng **giữ nguyên** dòng bắt buộc `- Độ phủ: tổng dòng x,x% · nhánh y,y%`, và §3 vẫn giữ gạch đầu dòng "Độ phủ mỗi gói bị chạm **và tổng** đều ≥ 90%". Ở phạm vi đích không có cách lấy hai số đó, reviewer buộc phải bỏ trống hoặc điền số cũ — đúng thứ K25 cấm. Chính bản review này gặp ngay | `.claude/skills/merge-review/SKILL.md:100`, `:59` | Dòng độ phủ nhận thêm nhánh "không đo (phạm vi đích) — file đổi: a.py 9x,x%/9x,x%"; gạch đầu dòng §3 thêm "(phạm vi đích: chỉ file đổi; hai số tổng lấy từ lượt đầy đủ gần nhất)" |
| P3-1 | P3 | R-33b, MNT-02 | "Verify tích hợp trên `main` sau gộp chỉ khi cây sau gộp khác **cây đã qua cổng**" — không nói rõ cổng *đầy đủ* hay *đích*. Đọc là "cổng bất kỳ" thì nhánh có các vòng sửa đích sẽ bỏ luôn verify tích hợp: **không lượt đầy đủ nào từng chạy trên cây được gộp** | `RULE-CODE.md:68` | Một từ: "cây đã qua **lượt đầy đủ**" |
| P3-2 | P3 | R-33b | `pyproject.toml` trong danh sách (2) đứng cạnh `conftest.py`, `uv.lock`, `.importlinter` nên đọc thành *file gốc*; `pyproject.toml` thành viên (phụ thuộc, hợp đồng import-linter, luật bảng của `coverage_gate`) cũng buộc chạy đầy đủ | `RULE-CODE.md:68` | Viết `**/pyproject.toml` |
| P3-3 | P3 | R-33b | Điều kiện (4) "đổi chữ ký/hành vi của tên công khai **mà module khác nhập**" không kèm cách kiểm nên không phản chứng được, mỗi người đọc một kiểu — cũng là lối thoát mà P2-4 đang dựa vào | `RULE-CODE.md:68` | Thêm cách kiểm: `git grep -l '<tên>' -- apps packages` lọc bỏ module của mình, còn kết quả → đầy đủ |
| P3-4 | P3 | R-33b, DB-03 | `docs/contracts.toml` không có trong danh sách (2) dù `tools/lint_migrations.py` đọc nó ở **bước 6**. Rủi ro thấp (chỉ người điều phối sửa được), nhưng danh sách đã nêu `docs/charter/*` thì nên nêu cả file này | `RULE-CODE.md:68` | Thêm `docs/contracts.toml` vào danh sách đường dẫn |
| P3-5 | P3 | R-33b, MNT-02 | `docs/charter/FIX.md` [7] ghi tuyệt đối: "NGHIỆM THU: `just verify` … đạt". R-33b lại cho phép vòng sửa (đúng hình dạng một FIX) chạy đích. Hiến chương thắng (CLAUDE.md) → worker FIX vẫn phải chạy đầy đủ, tức R-33b mất hiệu lực ở đúng chỗ nó tiết kiệm nhiều nhất. Câu "R-33 được thoả bằng…" chỉ nhắc R-33 | `RULE-CODE.md:68` vs `docs/charter/FIX.md:21` | Thêm "(kể cả nghiệm thu FIX, `docs/charter/FIX.md` [7])" vào câu về R-33; người điều phối sửa FIX.md [7] thành "`verify` theo phạm vi R-33b đạt" trong lần cập nhật hiến chương kế tiếp |
| N-1 | Nit | — | §3 giữ "timeout Bash >= 600000 ms" (10 phút) ngay cạnh số mới "~25 phút" — hai số chỏi nhau; phần trong ngoặc "chạy nền + log" mới là cách đúng | `.claude/skills/merge-review/SKILL.md:52` | "chạy nền, theo `docker logs -f`, lấy mã thoát bằng `docker wait`" (container verify tự `AutoRemove`) |
| N-2 | Nit | — | Trailer `Co-Authored-By: Claude Opus 5.5 <…>` lệch mẫu `Claude Opus 5` của các commit `Prompt: dieu-phoi` trước. Không ảnh hưởng `%(trailers)` | commit `4363f33` | Giữ một mẫu duy nhất |

Tổng: **0 P0 · 0 P1 · 5 P2 · 5 P3 · 2 Nit**.

## Đúng, và đã tự kiểm

- Ba file nói cùng một luật, không lệch nhau: `RULE-CODE.md` R-33b định nghĩa; `CLAUDE.md` bảng "Chạy cổng"
  trỏ về R-33b thay cho câu cũ "mọi worker, trước khi báo xong"; `SKILL.md` §3 áp dụng (lượt 1 đầy đủ,
  lượt ≥ 2 đích trừ khi chạm (2)–(6), tác giả chọn sai thì reviewer tự chạy đầy đủ, và ghi
  `Phạm vi kiểm:` vào phán quyết).
- Không mâu thuẫn R-12, R-33, R-36/R-37, R-38 hay mục "Case, coverage" của `CLAUDE.md`: R-33b giữ nguyên
  ngưỡng 90% dòng **và** nhánh, không cho `pragma`, không hạ ngưỡng, và nói rõ R-33 được thoả bằng
  "lượt đầy đủ gần nhất + các lượt đích sau nó".
- Lượt đầu của nhánh đi review vẫn **đầy đủ** — lưới an toàn này khiến các lỗ ở P2-1..P2-4 chỉ hở với những
  commit sửa **sau** lượt đầy đủ đó, nên không finding nào lên P1.
- Lý do kinh tế đứng được: 20 phút mỗi lượt pytest đầy đủ nhân với nhiều vòng sửa trong một module, và lần
  áp dụng đầu đã có bằng chứng (review lượt 2 của B2-05b, squash `2bc5931`).

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 3 | 0,30 |
| TEST – Kiểm thử | 7% | 3 | 0,21 |
| OBS, OPS – Vận hành | 5% | 3 | 0,15 |
| MNT – Bảo trì | 3% | 3 | 0,09 |
| **Tổng** | **100%** | | **4,50 / 5** |

## PHÁN QUYẾT: APPROVE (4,50/5)

R-33b làm đúng điều người dùng chốt ngày 2026-09-26, có số đo thật chống lưng, ba file nhất quán với nhau,
không trái `BE-00 §12` (hiến chương vốn đã có `VERIFY_TOUCHED`), và giữ nguyên mọi ngưỡng — không P0/P1,
nên không chặn merge. Năm P2 đều cùng một loại: danh sách điều kiện "đầy đủ" còn hở với những thứ **chỉ**
bước 5/6 bắt được (kiểm tĩnh của `coverage_gate`, lệch model ↔ DB, test phụ thuộc thứ tự chạy theo `NO-211`),
cộng một danh sách gói kể tên thiếu 5/10 gói và mẫu phán quyết còn bắt điền hai số độ phủ không đo được ở
phạm vi đích.

Điều kiện merge (R-38): mỗi P2 phải có một dòng `NO-<nnn>` trong `DEBT.md` **trước** khi gộp, chủ sở hữu
`dieu-phoi` (P2-1..P2-4 và P3-1..P3-5 trên `RULE-CODE.md`; P2-5 và N-1 trên
`.claude/skills/merge-review/SKILL.md`). Người điều phối được gộp ngay sau khi ghi nợ; sửa câu chữ theo cột
"Đề xuất" trong lần cập nhật luật kế tiếp, ưu tiên P2-1 và P2-2 vì hai lỗ đó cho `main` đỏ mà không ai chạy
lại lượt đầy đủ.
