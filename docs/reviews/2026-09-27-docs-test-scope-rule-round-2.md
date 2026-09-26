# Review merge `docs/test-scope-rule` → main — lượt 2

- Ngày: 2026-09-27 · Reviewer: phiên /merge-review (độc lập, R-37) · Commit đầu nhánh: `3ff23ba` ·
  Lượt 1: `docs/reviews/2026-09-27-docs-test-scope-rule.md` (`9c4b1e9`, APPROVE 4,50/5)
- Phạm vi soát: **chỉ vòng sửa** `git diff 4363f33..3ff23ba` — 3 file Markdown
  (`RULE-CODE.md`, `.claude/skills/merge-review/SKILL.md`, `docs/charter/FIX.md`), 7 thêm / 6 xoá.
- Phạm vi kiểm: **đích** — diff không có `.py`, không cấu hình công cụ, không migration, không dây;
  áp chính R-33b: không điều kiện (2)–(7) nào bị chạm (lượt đầy đủ của nhánh đã chạy ở lượt 1).
- Cổng: phạm vi đích; `bash tools/verify/run.sh verify --steps 1,2` mã thoát **0**
  (bước 1 `ruff format --check` đạt — 756 file; bước 2 `ruff check` đạt; log `r33b-r2-verify12`, pane RUNNER).
  Bước 3–8 **chưa chạy** (không có file mã nào đổi — E.10).
- Độ phủ: không đo (phạm vi đích) — file đổi: không có file mã.

## Sổ theo dõi finding lượt 1

| Lượt 1 | Trạng thái | Bằng chứng trong diff |
|---|---|---|
| P2-1 kiểm tĩnh `coverage_gate` không chạy ở lượt đích | **đóng (còn hở hẹp → R2-3)** | (3) mới: "thêm, xoá hay đổi tên file/thư mục `.py` (kể cả file test mới) — kiểm tĩnh của `coverage_gate` (bước 5) chỉ chạy ở lượt đầy đủ". Đóng luôn lỗ xoá file test làm tụt độ phủ đơn vị |
| P2-2 sửa model không migration → bước 6 đỏ | **đóng** | (2) mới tính **mọi** `packages/**` "kể cả `packages/db/models/*`, migration" là đầy đủ; đã kiểm không có model SQLAlchemy nào nằm ngoài `packages/db` (`grep -rln "Mapped\[" apps` rỗng) |
| P2-3 test phụ thuộc thứ tự chạy (NO-211) | **đóng một nửa (→ R2-2)** | (7) mới, nhưng chỉ nói chiều "xanh ở lượt đích phải xác nhận lại"; chiều NO-211 thật (xanh ở cổng đầy đủ, **đỏ khi chạy lẻ**) chưa có |
| P2-4 danh sách kể tên thiếu 5/10 gói | **đóng** | (2) viết lại theo **loại trừ** ("bất kỳ file nào ngoài thư mục module"), nên không còn gói nào lọt; thêm `apps/*/celery_main.py`, `apps/ml/runtime/**`, `.github/**` |
| P2-5 mẫu phán quyết bắt điền độ phủ tổng | **đóng** | Mẫu §6 nhận nhánh "không đo (phạm vi đích) — file đổi: …"; gạch đầu dòng §3 và chính R-33b nhắc K25 "không chép số cũ" |
| P3-1 "cây đã qua cổng" mơ hồ | **đóng, mạnh hơn đề xuất** | "trùng cây đã qua lượt **đầy đủ**" + câu mới "nhánh có vòng sửa kiểm đích sau lượt đầy đủ → chạy đầy đủ một lần (trước khi gộp hoặc ngay sau)" — đây là chốt giữ cho toàn bộ luật |
| P3-2 `pyproject.toml` gốc hay thành viên | **đóng** | `**/pyproject.toml` |
| P3-3 (4) không có cách kiểm | **đóng, đã chạy thử** | `git grep -l "<đường.module>" -- apps packages ':!apps/<app>/<module>'`; tôi chạy thử pathspec `':!…'` với `packages.vision` → thoát 0, đúng loại trừ. Lệnh grep theo *đường module* thay vì theo tên hàm là xấp xỉ **thừa an toàn** (chạy đầy đủ nhiều hơn, không ít hơn) — chấp nhận được |
| P3-4 `docs/contracts.toml` | **đóng** | Thêm cả `docs/contracts.toml` và `docs/contracts/**` |
| P3-5 `FIX.md` [7] tuyệt đối | **đóng** | `docs/charter/FIX.md:21`: "lượt đầu của nhánh FIX luôn đầy đủ, vòng sửa sau review theo phạm vi RULE-CODE.md R-33b" |
| N-1 "timeout Bash >= 600000 ms" | **đóng** | "~25 phút > trần 10 phút của lệnh Bash → chạy nền + log, đọc mã thoát từ log" — đúng: `run.sh` in `mã thoát: <n>` vào log |
| N-2 trailer "Claude Opus 5.5" | **đóng bằng giải thích** | Tên model thật của phiên điều phối; không phải lệch mẫu. Rút lại finding |

`SKILL.md` §3 đã đổi "(2)–(6)" → "(2)–(7)" khớp số điều kiện mới. Không còn câu cũ nào sót
("mọi worker, trước khi báo xong", "~2-4 phút" — grep rỗng). Bảng Markdown nguyên vẹn: hàng R-33b
4 dấu gạch dọc, 1 dấu đã escape → đúng 2 ô. Dòng mẫu độ phủ có dấu gạch dọc nhưng nằm **trong khối
mã** của §6 nên không vỡ bảng.

## Finding mới hoặc còn lại

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| R2-1 | P2 | R-33b, MNT-02 | "ngoài **thư mục module của prompt** (`apps/<app>/<module>/**`)" chỉ đúng với prompt sở hữu thư mục dưới `apps/`. Bằng chứng: `changes/B2-05a.md:1` — B2-05a sở hữu `packages/vision/preprocess` **và** `packages/vision/quality`: vừa là prompt sở hữu **gói**, vừa sở hữu **hai** thư mục. Với chủ sở hữu kiểu này, mọi thay đổi của họ đều "ngoài thư mục module" → **luôn đầy đủ**, tức R-33b không tiết kiệm gì ở đúng nơi test chậm nhất (vision/ML) — trái ý người dùng chốt 2026-09-26. Các prompt `B0-0x` sở hữu `packages/{core,db,storage,messaging,…}` cùng hoàn cảnh. Chiều đọc còn lại cũng có rủi ro: nếu ai hiểu "thư mục module" = gói mình sở hữu thì chủ `packages/core` (203 file nhập) sẽ tự cho mình chạy đích — lỗ này may thay bị điều kiện (4) chặn lại | `RULE-CODE.md:68` | Định nghĩa theo **sở hữu** và ở số nhiều: "ngoài **các thư mục prompt sở hữu** (cột Sở hữu / dòng đầu `changes/<mã>.md`: `apps/<app>/<module>/**` hoặc `packages/<gói>/<thư mục>/**`)", **kèm sàn cứng**: "`packages/{core,db,testing,messaging,storage,observability,domain}/**`, `**/pyproject.toml`, `uv.lock`, `conftest.py`, `.importlinter`, `tools/**`, `deploy/**`, `.github/**`, `docs/charter/*`, `docs/contracts*` là đầy đủ **kể cả với chủ sở hữu**" |
| R2-2 | P3 | R-33b, TEST-02 | (7) chỉ nói một chiều ("test chỉ xanh ở lượt đích phải được xác nhận lại"). Chiều mà `NO-211` thật sự mô tả là ngược lại: xanh trong cổng đầy đủ, **đỏ khi chạy lẻ**. Worker gặp đỏ giả ở lượt đích sẽ đi sửa một lỗi không tồn tại — đúng bẫy R-19 (vá triệu chứng) và K24 (nới assert để xanh) | `RULE-CODE.md:68` | Thêm vào cuối (7): "và **đỏ** chỉ xuất hiện ở lượt đích phải xác nhận lại ở lượt đầy đủ trước khi coi là lỗi thật" |
| R2-3 | P3 | R-33b, TEST-05 | (3) chỉ bật với file/thư mục `.py`; nhưng kiểm tĩnh của `coverage_gate` còn bắt hai thứ **không cần file `.py` mới** và có thể nằm **trong** thư mục module: (a) `# pragma: no cover`/`no branch`, `# mypy: ignore-errors`, `@no_type_check` thêm vào file có sẵn; (b) file cấu hình công cụ cấm (`.coveragerc`, `pytest.ini`, `ruff.toml`, `setup.cfg`, `tox.ini`, `mypy.ini`) đặt trong `apps/<app>/<module>/` — `SCAN_DIRS` có `apps` (`tools/coverage_gate.py:29`–`45`, `:60`). Cả hai là hành vi lách cổng nên reviewer vẫn grep được ở §2, rủi ro thấp | `RULE-CODE.md:68` | (3) → "… hoặc thêm file cấu hình công cụ, hoặc thêm `pragma:`/`# mypy: ignore-errors`/`@no_type_check` vào file có sẵn" |
| R2-4 | P3 | MNT-02 | Danh sách dừng sớm §2 vẫn ghi: diff đụng `docs/charter/*` là **REJECT ngay**, không có ngoại lệ cho người điều phối. Chính commit `3ff23ba` sửa `docs/charter/FIX.md` — hợp lệ vì trailer `Prompt: dieu-phoi` và CLAUDE.md nói "chỉ người điều phối", và chính lượt 1 yêu cầu sửa file đó. Đọc đúng chữ thì skill sẽ REJECT bản sửa mà nó vừa đòi | `.claude/skills/merge-review/SKILL.md:41` | "… trừ commit của **người điều phối** (trailer `Prompt: dieu-phoi`) — CLAUDE.md cho phép; reviewer ghi rõ căn cứ trong phán quyết" |
| R2-5 | P3 | R-33b | (7) không có cách kiểm, trong khi (4) vừa được cấp một lệnh cụ thể: "module có nợ mở về test phụ thuộc thứ tự chạy" — các dòng `DEBT.md` diễn đạt tự do nên không grep được, worker sẽ bỏ qua điều kiện này | `RULE-CODE.md:68` | Đánh dấu cố định cho loại nợ này trong `DEBT.md` (vd `[thứ tự chạy]` ở cột trạng thái) rồi (7) thêm: "kiểm: `grep -n '\[thứ tự chạy\]' DEBT.md` có dòng `mở` chạm module mình" |
| R2-N1 | Nit | — | `docs/charter/FIX.md` [7] nay trỏ sang `RULE-CODE.md` (file ngoài hiến chương) trong khi CLAUDE.md quy định "mâu thuẫn → hiến chương thắng". Uỷ quyền một chiều và tường minh nên chấp nhận được; ghi lại để lần sau không ai "sửa lại cho đúng tầng" | `docs/charter/FIX.md:21` | Giữ nguyên; nếu muốn sạch tầng thì chuyển chính bảng phạm vi vào `BE-00 §12` và để R-33b trỏ lên |

Tổng: **0 P0 · 0 P1 · 1 P2 · 4 P3 · 1 Nit** (lượt 1: 5 P2 · 5 P3 · 2 Nit).

## Nợ và sổ nợ

- Năm P2 của lượt 1 được **sửa**, không hoãn, nên R-38 không đòi dòng `DEBT.md` nào cho chúng —
  đã kiểm: `git log 9c4b1e9..HEAD -- DEBT.md` trên `main` rỗng, và đó là đúng.
- `NO-211` vẫn `mở` và nay được R-33b (7) trích dẫn trực tiếp; không phải nợ của nhánh này (chủ: B1-03).
- Nợ nên ghi trước khi gộp (R-38): **R2-1** (P2) — một dòng `NO-232`, chủ `dieu-phoi`, nếu không sửa
  ngay câu chữ. Bốn P3 và Nit có thể gộp vào cùng một dòng hoặc sửa trực tiếp; không chặn merge.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 4 | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 3 | 0,09 |
| **Tổng** | **100%** | | **4,87 / 5** |

## PHÁN QUYẾT: APPROVE (4,87/5)

Vòng sửa đóng **10/11** finding của lượt 1 và đóng bằng cách tốt hơn đề xuất ở ba chỗ: (2) chuyển từ danh
sách kể tên sang luật loại trừ (không gói nào lọt được nữa), P3-1 thêm hẳn câu "nhánh có vòng sửa kiểm đích
sau lượt đầy đủ → chạy đầy đủ một lần", và (3) bao luôn việc xoá file test. Lệnh kiểm của (4) tôi đã chạy
thử, pathspec `':!…'` hợp lệ. Cổng đích xanh (mã thoát 0), không file cấm nào bị chạm trái phép —
`docs/charter/FIX.md` do người điều phối sửa (trailer `Prompt: dieu-phoi`), đúng thẩm quyền CLAUDE.md và đúng
yêu cầu P3-5 của lượt 1.

Còn một P2 **mới do câu chữ mới sinh ra**: định nghĩa "thư mục module của prompt" chỉ phủ `apps/<app>/<module>`,
nên các prompt sở hữu gói — bằng chứng `changes/B2-05a.md:1` với **hai** thư mục dưới `packages/vision` — sẽ
luôn phải chạy đầy đủ, mất đúng phần tiết kiệm mà luật sinh ra để có. Không P0/P1 nên không chặn merge.

Điều kiện gộp (R-38): sửa một câu của (2) theo cột "Đề xuất" của R2-1 (định nghĩa theo sở hữu, số nhiều, kèm
sàn cứng) **hoặc** ghi `NO-232` cho nó trước khi gộp; R2-2..R2-5 và R2-N1 không chặn. Tôi khuyến nghị sửa tại
chỗ thay vì ghi nợ: một câu, và chủ sở hữu gói gặp ngay ở lần dùng đầu tiên.
