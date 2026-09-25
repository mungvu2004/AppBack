# Review merge feature/b2-02-members-settings → main

- Ngày: 2026-09-25 · Reviewer: phiên /merge-review (độc lập, không sửa mã, không merge) · Commit đầu nhánh: `5fb4e8ba2e9c`
- Cổng: `bash tools/verify/run.sh verify` mã thoát **0** (chạy tại chỗ trong worktree review, foreground pane RUNNER; log
  `…/scratchpad/verify-review-b2-02.log`, dòng `EXIT=0`, pytest 879 s)
- Test: **4137 passed, 4 deselected, 0 hỏng** (collected 4141)
- Độ phủ: tổng **dòng 99,46% · nhánh 98,38%**; `apps/api/project_members` 100,00/100,00; `apps/api/project_settings`
  100,00/100,00; `packages/db` 95,49/95,54; `packages/testing` 99,51/98,95; tập file bị chạm 100,00/100,00
- Phạm vi chấm: `git diff main...HEAD` trừ `packages/testing/fixtures/services.py` (FIX-106 của B0-01, đi `main` bằng
  phiên review riêng). 522 dòng logic + ~1 550 dòng test, 30 file.

## Bảng cổng (mã thoát thật, E.10)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | /work/contract-node/3c583539a0314ecd |
| 1 | ruff format --check | đạt | |
| 2 | ruff check | đạt | |
| 3 | mypy --strict | đạt | |
| 4 | lint-imports | đạt | |
| 5 | coverage run -m pytest → coverage_gate | đạt | 4137 passed |
| 5b | pytest -m perf → case_gate | đạt | perf: 0 đơn vị bị chạm |
| 6 | lint_migrations → migrate_check | đạt | 9 revision, đúng 1 head, model khớp DB, tên CHECK khớp model |
| 7 | H1 H3 H4 H5 (tools.contract.check) | đạt | Smoke đạt (23 module schema, 83 mục bản đồ); Bản đồ đủ 83/83; Thao tác đã mount 41/83; H1 đạt (986 mẫu response); H1 ngữ cảnh đạt (10); H3 đạt (10 khoá, 3 vai); **H4 không áp dụng** (B3-05 chưa hợp nhất — đúng BE-00 §12); H5 đạt (3 khung SSE) |
| 8 | openapi | đạt | |

`case_gate` bốn `op` mới — **thiếu = 0**, đều `đạt`:

| op | bắt buộc | tìm thấy |
|---|---|---|
| `members_add_member` | C01 C02 C03 C04 C05 C06 C07 C08 C10 C11 C12 C13 C14 C16 C17 C18 C22 C25 | đủ 18/18 |
| `members_remove_member` | C01 C04 C05 C06 C07 C08 C10 C12 C13 C14 C16 C17 C18 C22 C25 | đủ (C16 `waive = "DELETE không có thân"`) |
| `settings_read_settings` | C01 C04 C05 C06 C08 C12 C13 C17 C25 | đủ 9/9 |
| `settings_replace_settings` | C01 C02 C03 C04 C05 C06 C07 C08 C09 C09b C12 C13 C14 C16 C17 C18 C25 | đủ 17/17 |

Số của báo cáo tác giả (`bao-cao-B2-02.md`) **khớp từng con số** với lượt chạy độc lập này.

## Đã tự kiểm (không tin báo cáo)

- **Điều kiện dừng sớm:** cây làm việc rỗng; 7 commit đều đúng Conventional Commits + trailer `Prompt: B2-02`
  (5ac987b thêm `Fix: FIX-106`); có `changes/B2-02.md` (6 dòng); **không** đụng `docs/charter/*`, `openapi.json`,
  `uv.lock`, `tools/**`, `conftest.py`, `pyproject.toml`, `.importlinter`, `APPFRONT_SHA`; không tạo file cấu hình
  công cụ riêng; không `pragma: no cover`, không `type: ignore`, hai `# noqa: S603` đều có mã + lý do; không
  `skip`/`xfail` mới.
- **K08 / quyền (SEC):** `require_project` là dependency đầu của cả 4 route; `AppRoute` chèn `dependencies=` vào
  **đầu** cây nên `_edit_gate` chạy **trước** `_add_limit` (vá 651f01f) — kiểm lại bằng `apps/api/core/routing.py:208-215`
  và test `test_members_add_member__C11_permission_before_limit` (viewer luôn {403}, người ngoài luôn {404} qua 5 lượt
  với hạn mức 3). 404 `resource:"project"` thắng 403 ở C06 của cả 4 op; `{user_id}` sai mẫu → 404 `resource:"member"`
  trước mọi truy vấn (`service.py:55-58,107`).
- **SEC-14/SEC-02:** "không có tài khoản" và "bị vô hiệu" đi chung `_require_available` → một mã, **một thân**
  (test so hai thân trừ `requestId`). Email chỉ qua `validate_wire_email` ở biên schema (K37; test chặn `ánh@`, U+017F,
  U+212A). `added_by`, `actor_id`, `last_writer_id` đều lấy từ `ProjectAccess.principal` (K05); không đường nào đọc
  người thực hiện từ thân. `users.email_normalized` có unique một phần trên dòng chưa xoá mềm nên
  `scalar_one_or_none()` của N3 không thể ném `MultipleResultsFound`.
- **CON / K07:** N6 quyết thắng thua bằng **một** câu SQL — `INSERT … ON CONFLICT (project_id) DO NOTHING RETURNING`
  (base 0) hoặc `UPDATE … SET revision = revision + 1 WHERE project_id = :p AND revision = :base RETURNING`
  (`service.py:62-76`); không đọc–so–ghi trong Python. Chỉ khi 0 dòng mới `find_row` để phân biệt C09b. Truy lại bốn
  đường đua dưới READ COMMITTED (cùng người/khác người × base 0/base > 0) đều ra đúng kết quả hợp đồng; test C14
  chạy thật trên Postgres cho `[200, 409]` và revision cuối = base + 1 ở cả base 0 và base 1.
- **C09b** đúng ba điều kiện của [6].5 (`revision = base + 1` **và** cùng `last_writer_id` **và** cùng
  `last_body_sha256`); băm ổn định vì `Decimal` đã `quantize` nên `str()` cho số chữ số cố định, và `notes` đã NFC —
  bản NFD gửi lại vẫn là C09b (test C16).
- **CON N4:** `lock_editor_ids` (`FOR UPDATE OF project_memberships`, `user_id ASC`) là khoá **đầu tiên**, rồi
  membership mục tiêu `FOR UPDATE`, `touch_project` là lời khoá **cuối** — đúng thứ tự BE-00 §7, không tạo chu trình
  với N3/N6 (cả ba đều khoá bảng của mình trước, `projects` sau cùng). C14 gỡ lẫn nhau cho `[200, 422 MEMBER_LAST_EDITOR]`,
  còn 1 người sửa.
- **CON-02/K17:** N3 để `idempotency="auto"` (`uses_idempotency` = True vì POST, không `versioned`); guard idempotency
  nằm **cuối** cây dependency nên chạy sau quyền và hạn mức. Test C10 chứng minh lặp khoá cùng thân → cùng response và
  **một** lượt sink, khác thân → 422 `IDEMPOTENCY_KEY_REUSED`, sink vẫn 1 lượt. Sink chạy trong giao dịch, ném thì
  lỗi nổi lên (không `except` rộng) → 500 + rollback, kiểm bằng test: 0 membership, 0 dòng nhật ký.
- **Cổng mời:** `invite_sink` đếm **tổng** phần tử qua mọi module (0 → no-op, 1 → dùng, > 1 → `RuntimeError`), không
  bắt `ImportError`, `extensions` nhập muộn trong thân hàm và `AsyncSession`/`Clock` chỉ dưới `TYPE_CHECKING`; test
  tiến trình con nhập `sinks` **và gọi** `invite_sink()` khi `fastapi`, `jwt`, `argon2` bị chặn. `override` ở
  `APP_ENV=dev` → `RuntimeError` (có test). Cả hai `__init__.py` chỉ docstring (kiểm bằng AST trong test).
- **LOG-02 / W2-W3:** `snapToleranceMm` `strict=True` (bool và float bị loại), `confidenceThreshold` và
  `defaultScaleMmPerPx` chỉ nhận số JSON (bool/chuỗi/NaN/∞ → 422), đổi `Decimal(str(x))` rồi `ROUND_HALF_UP`;
  `notes` trim → NFC → cấm Cc trừ `\n\t` → cấm 11 ký tự định hướng (đối chiếu từng codepoint: U+200E, U+200F,
  U+202A–U+202E, U+2066–U+2069 — **đủ, không thừa**) → 1–500. Response là `float` (số JSON), `notes` NULL → vắng khoá.
  Mặc định khi chưa có dòng đúng `projectSettingsGateway.ts:141-149`.
- **DB:** expand thuần, một bảng mới, **đúng 1 head** (`r20260925_b2_02` ← `r20260923_b2_03`), FK
  `projects.id ON DELETE CASCADE` (có test xoá cứng dự án), downgrade có, 8 CHECK khớp model (bước 6 tự so).
- **R-01/R-02:** mọi hàm/lớp/module trong 14 file mã và 8 file test đều có docstring (ruff không bật nhóm `D` nên
  kiểm tay). `# noqa` đều có mã và lý do.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P2** | MNT-05 | Nhánh 522 dòng logic (> 400 của checklist). **Miễn, có lý do đứng được:** đây là trọn vẹn một prompt (4 `op`, 2 module do chính B2-02 sở hữu), đã được chia sẵn thành hai nhánh worker (`f221c06` settings, `ffd73fc` members) và vào `main` bằng **một** squash theo BE-00 §13.2; tách nhỏ hơn nghĩa là tách prompt. Hai module độc lập, mỗi module 100/100 độ phủ | toàn nhánh | không tách; ghi nhận để prompt cỡ này lần sau vẫn giữ hai module tách bạch |
| 2 | P3 | LOG-02 | `Confidence` kiểm dải **sau** khi làm tròn, nên giá trị âm rất nhỏ lọt: `confidenceThreshold: -0.0004` → `Decimal("-0.000")`, `ge=0` cho qua (Decimal `-0.000 == 0`), CHECK `BETWEEN 0 AND 1` cũng qua, và dây trả **`-0.0`** thay vì 422 cho một trường khai dải 0–1. (Đo tại chỗ: `-0.0004 → -0.000, ge0 True, float -0.0`; `-0.4` vẫn 422 đúng) | `apps/api/project_settings/schemas.py:55` (hàm `convert` `:43-49`) | chặn dấu âm ngay trong `convert`, hoặc thêm `Field(ge=0)` trên giá trị **thô** trước `BeforeValidator`; thêm ca `-0.0004` vào tham số C02 |
| 3 | P3 | TEST-01 / R-02 | Docstring của C01 hứa kiểm "membership `added_by` = người gọi (K05)" nhưng **không assert nào** chạm cột `added_by` — grep cả module chỉ thấy nó ở `service.py:79`. Mã hiện đúng, nhưng nếu ai đó nối `added_by` sai nguồn thì cổng vẫn xanh | `apps/api/project_members/tests/test_add_member.py:30` | thêm assert đọc `ProjectMembership.added_by == actor.id` trong C01 (hoặc sửa docstring cho khớp việc test thật làm) |
| 4 | P3 | R-07 | `_BIDI` và `_clean_notes` là bản chép của `_BIDI`/`clean_text` ở `apps/api/projects/schemas.py:30,34-47` (khác đúng một điểm: cho phép `\n\t`). `clean_text` là hàm **công khai** nên chỗ sửa gốc nằm ở file B2-01 (K27) — tác giả có nêu trong "Lệch khỏi prompt" nhưng **không mở dòng `DEBT.md`** | `apps/api/project_settings/schemas.py:22,26-36` | ghi một dòng `NO-<nnn>` (P3): đưa phép kiểm Cc + định hướng về `packages/core/text.py` với tham số `allowed_controls`, hai module cùng gọi; giao FIX cho chủ B2-01 |
| 5 | P3 | DB-01 | `[5]` của prompt ghi `last_body_sha256 char(64)`; model và migration dùng `Text` + CHECK `char_length = 64`. Kết quả tương đương (thực ra tốt hơn `char(64)` vì không đệm khoảng trắng) nhưng **không** được khai trong mục "Lệch khỏi prompt" của báo cáo | `packages/db/models/project_settings.py:36`, `packages/db/migrations/versions/r20260925_b2_02_project_settings.py:46` | giữ nguyên mã; bổ sung một dòng "Lệch khỏi prompt" để lần sau không ai tưởng là sót |
| 6 | Nit | API-01 | Route N3 chỉ khai `status_code=201`; nhánh "đã là thành viên → 200" không có trong `responses` nên `openapi.json` không mô tả 200, dù BE-BIND N3 ghi cả hai. Không ảnh hưởng FE (cùng `UserSchema`, `toAppError` chỉ phân loại lỗi) | `apps/api/project_members/router.py:42-47` | `responses={200: {"model": UserOut, "description": "đã là thành viên"}}` |
| 7 | Nit | R-10 | `if user_id in editors:` là điều kiện thừa: `_require_not_last_editor` chỉ ném khi `editors == [user_id]`, đã bao hàm phép `in` | `apps/api/project_members/service.py:117-118` | gọi thẳng `_require_not_last_editor(editors, user_id)` |
| 8 | Nit | MNT-01 | `apps/api/project_members/tests/__init__.py` rỗng, trong khi `apps/api/project_settings/tests/__init__.py` có docstring | `apps/api/project_members/tests/__init__.py` | thêm một dòng docstring cho đồng bộ |

Không có finding **P0** hay **P1**.

### Đối chiếu "Lệch khỏi prompt" của tác giả

| Điểm tác giả nêu | Phán quyết |
|---|---|
| Nhánh chứa FIX-106 (B0-01) | **chấp nhận** — đúng như người điều phối dặn, đã có phiên review riêng, không chấm ở đây |
| Câu commit theo mẫu `CLAUDE.md`, merge dùng `chore` | **chấp nhận** — `ghi-chu-hop-dong.md` mục 2 đã chốt; hook `commit-msg` chặn `merge:` |
| `user_out(row, storage)` async | **chấp nhận** — chữ ký thật `apps/api/projects/wire.py:134`, đã tra lại |
| `ProjectSettingsWriteIn` thay `versioned()` | **chấp nhận có lưu ý** — hình dạng dây giống hệt (`{baseVersion ≥ 0, body}`, camelCase, `extra="forbid"`), guard 428 do `route_options(versioned=True)` cấp nên không phụ thuộc model; khác duy nhất là `base_version` ở đây `strict=True` (chặt **hơn** `versioned()`). N6 là route GV đầu tiên nên chưa lệch với ai; khi route GV thứ hai dùng `versioned()` thì hai đường sẽ khác độ chặt — đáng thống nhất lúc đó, không chặn bây giờ |
| `_BIDI` khai lại (R-07) | **thành finding #4** (lý do đứng được nhưng thiếu dòng `DEBT.md`) |
| Revision chép tay từ skeleton | **chấp nhận** — bước 6 đã chứng minh: đúng 1 head, upgrade/downgrade/upgrade lại, model khớp DB, tên CHECK khớp model |
| Sink ném → 500 `INTERNAL` + rollback | **chấp nhận** — [6].5 chỉ đòi "không nuốt lỗi"; 500 là hệ quả đúng, có test chứng minh 0 membership + 0 nhật ký |
| Vá gộp: `require_project` trước `rate_limit` | **chấp nhận** — đã kiểm lại ở mã khung lẫn test hành vi |

Một điểm báo cáo nêu mà tôi **không** dựng lại được: bốn dòng `print` C14 ở mục "C14 (Postgres thật)" không xuất hiện
trong log vì pytest nuốt stdout của test xanh. Nội dung ấy đã được các `assert` của chính bốn test mang (status hai bên,
số membership, số người sửa còn lại, revision cuối) và bốn test đều xanh, nên không ghi thành finding.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 4 | 0,60 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 4 | 0,40 |
| TEST – Kiểm thử | 7% | 4 | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 3 | 0,09 |
| **Tổng** | **100%** | | **4,62 / 5** |

## PHÁN QUYẾT: APPROVE

Cổng xanh thật (mã thoát 0, 8/8 bước, 4137 test, độ phủ hai con số riêng đều vượt ngưỡng ở cả hai module mới và toàn
repo), và phần khó của prompt đã làm đúng chỗ khó: thứ tự 404-trước-403 ở cả bốn `op`, hạn mức sau cổng quyền, một
câu SQL duy nhất quyết thắng thua cho ghi có version với C09b ba điều kiện, thứ tự khoá cố định `lock_editor_ids` →
membership → `touch_project`, và cổng mời tách sạch khỏi `fastapi` để B4-02 cắm vào. Ba đường đua C14 đều được dựng
lại bằng Postgres thật, không mock. Không có P0, không có P1; điểm 4,62 ≥ 4,0.

Năm finding còn lại đều không chặn merge. Đề nghị người điều phối mở **hai** dòng `DEBT.md` mức P3 sau khi gộp —
finding #4 (gom phép kiểm ký tự điều khiển/định hướng về `packages/core/text.py`, FIX thuộc chủ B2-01) và finding #2
(chặn `confidenceThreshold` âm trước khi làm tròn) — còn #3, #5, #6, #7, #8 tác giả tự quyết khi chạm lại file.

Phiên này **không** merge: việc gộp `feature/b2-02-members-settings` vào `main` bằng squash thuộc phiên điều phối.
