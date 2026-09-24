# Review merge `feature/b1-05-user-admin` → main — lượt 2 (vòng sửa 1)

- Ngày thật: **2026-09-25** · Reviewer: phiên `/merge-review` (cùng terminal lượt 1, worktree `b1-05-review`, HEAD tách `1f99c7e`)
  · Tên tệp giữ tiền tố `2026-09-24` theo đúng đường dẫn người điều phối giao, để nằm cạnh phán quyết lượt 1.
- Lượt 1: **APPROVE 4,25/5** (`docs/reviews/2026-09-24-feature-b1-05-user-admin.md`, trên `main` `6a82c83`), 4 finding.
  Finding 3 và 4 đã thành `DEBT.md` **NO-206**, **NO-207** (`main` `e6a679b`) — **không** chấm lại ở đây.
- Phạm vi lượt này: **chỉ** `git diff 7587f46..1f99c7e` — 1 commit, 4 file, **+48/−11**
  (`apps/api/users/schemas.py` 17 · `service.py` 9 · `tests/test_delete.py` +19 · `tests/test_invite.py` +14).
  Spec vòng sửa: `backend/dieu-phoi/chay/B1-05/spec-sua1.md`.
- `git diff --name-only main...HEAD` (2 commit) vẫn nằm **trọn** whitelist: 15 tệp dưới `apps/api/users/**`
  + `changes/B1-05.md`. `git status --porcelain` rỗng. Dòng đầu commit 61 ký tự, đúng Conventional Commits,
  khối trailer là đoạn cuối (`Prompt: B1-05` + `Co-Authored-By`), không `--no-verify`, **commit mới** chứ không amend.

## Cổng — ai chạy cái gì

Theo yêu cầu của người điều phối, reviewer **không** chạy lại cổng đầy đủ lượt này.

| Kiểm | Ai chạy | Kết quả |
|---|---|---|
| Cổng đầy đủ `verify` | tác giả, một lượt | `backend/dieu-phoi/chay/B1-05/gate2.log` — **mã thoát 0**, bước 1–8 `đạt`; H4 `không áp dụng` (B3-05 chưa hợp nhất, đúng BE-00 §12); 4011 passed / 0 failed / 4 deselected, 972 s |
| `verify --steps 1,2,3,4` | **reviewer, tại chỗ** | `1 ruff format: đạt · 2 ruff check: đạt · 3 mypy --strict: đạt · 4 lint-imports: đạt` — **mã thoát 0** |
| `coverage run --branch -m pytest apps/api/users -q` | **reviewer, qua `run.sh shell`** | **114 passed, 0 failed**, 76,3 s, mã thoát 0 |
| `coverage report --include='apps/api/users/*'` | **reviewer** | 305 câu lệnh, **0 miss**; 34 nhánh, **0 thiếu** → **dòng 100 % · nhánh 100 %** (từng tệp: `__init__` 100 · `errors` 100 · `router` 100 · `schemas` 100 · `service` 100) |

**Đối chiếu với `gate2.log` — không có số nào lệch.** Độ phủ `apps/api/users` 100 %/100 % trùng khít;
114 test module khớp đúng 111 của lượt 1 cộng 3 test mới (`test_delete` thêm 1 test parametrize 2 tham số,
`test_invite` thêm 1). Tổng repo 99,45 %/98,36 % trong `gate2.log` bằng đúng lượt 1, hợp lý vì diff chỉ thêm
test và không thêm dòng mã nào chưa được phủ.

Hai ghi chú về `gate2.log`, cả hai đều **không** thành finding:

- Tác giả tự khai đã **kill một lượt `verify` đầu** vì còn lỗi E501 trong docstring test. Lượt bị kill không sinh
  kết quả nào nên không có chuyện chọn số đẹp; lượt duy nhất chạy trọn là `gate2.log`. Khai báo minh bạch, đúng
  tinh thần "đúng một lần" của spec.
- `openapi.json` nở từ 76 802 → **76 825 byte** (+23). Giải thích hết bằng docstring `InviteBody` dài thêm
  (+18 byte UTF-8, cộng chênh lệch escape JSON của ký tự ngoài ASCII): docstring lớp đi thẳng vào `description`
  của schema. **Không** có trường hay ràng buộc nào đổi — hai thay đổi duy nhất chạm model Pydantic là thêm một
  `field_validator` (mode `after`, không ảnh hưởng JSON Schema) và sửa docstring; `Field(min_length=1)` giữ nguyên.
  Bước 7 vẫn đúng **871 mẫu H1** và **10 khoá/3 vai H3** y hệt lượt 1.

## Finding 1 lượt 1 (P2, SEC-03/K37) — **đã sửa đúng**

`apps/api/users/schemas.py:78-82`:

```python
@field_validator("confirm_email")
@classmethod
def _wire_email(cls, value: str) -> str:
    """`confirmEmail` cũng qua `validate_wire_email` (K37): chuỗi ngoài ASCII không được chuẩn hoá thành trùng."""
    return validate_wire_email(value)
```

Đúng khuôn `SignInBody._wire_email` (`apps/api/auth/router.py:76-79`) mà lượt 1 đề nghị. `_require_confirm`
(`service.py:111-114`) **giữ nguyên**, nên đường hoa-thường-khác vẫn 200 — `validate_wire_email` trả `nfc(trimmed)`
chứ không `casefold`, và test cũ `test_users_delete_user_confirm_email_is_compared_normalized` vẫn xanh.

Test mới `tests/test_delete.py:188-205` `test_users_delete_user_confirm_email_rejects_non_ascii_folding`,
parametrize 2 tham số `("ksu", U+212A)` và `("sa", U+017F)`. Đã kiểm **assert thật**, không phải test rỗng nghĩa:

- `confirm = target.email.replace(local[0], fold_char)` thay đúng **một** ký tự (`'k'` chỉ xuất hiện một lần trong
  `ksu@example.com`; `'s'` chỉ một lần trong `sa@example.com`), và có `assert confirm != target.email` chốt rằng
  chuỗi gửi đi **khác** email thật;
- khẳng định bộ ba `(422, "VALIDATION", "confirmEmail")` — đúng mã và đúng `field` camelCase mà lượt 1 đòi;
- khẳng định `(await reload(db_session, target.id)).deleted_at is None` — người **không** bị xoá.

Đây là lưới chắn hồi quy thật: bỏ validator đi thì `normalize_email('Ksu@example.com') == 'ksu@example.com'`
(reviewer đã đo lại ở lượt 1) ⇒ khớp ⇒ 200 + xoá. Test sẽ đỏ. **Finding 1 đóng.**

## Finding 2 lượt 1 (P3, LOG-01) — **đã sửa đúng**

Bỏ trùng rời khỏi `schemas.py` (`_validate_emails` giờ chỉ `[validate_wire_email(v) for v in values]`, vẫn ở
**mức cả danh sách** nên lỗi vẫn mang `field:"emails"` chứ không `emails.0` — K37 giữ nguyên), và trần đếm trên
**danh sách gốc** tại **một** chỗ duy nhất `service.invite_users:412` → `_require_batch_size` (`service.py:117-120`).
Không có chỗ kiểm thứ hai — reviewer đã `grep` cả module.

Bỏ trùng chuyển xuống `service.py:413-417`. Đã kiểm **tương đương và không hồi quy**:

- `first_seen: {email_normalized → email gốc đầu tiên}` giữ thứ tự chèn = thứ tự xuất hiện đầu (K20, "giữ thứ tự đầu").
- `keys = {email: key for key, email in first_seen.items()}` là phép **đảo không mất mát**: vì
  `first_seen[k] = e` luôn thoả `normalize_email(e) == k` và `normalize_email` là một hàm, nên không hai khoá nào
  chia sẻ cùng một giá trị `e`.
- `list(keys.values())` cấp cho `_lock_by_emails` đúng tập khoá duy nhất; vòng
  `sorted(keys.items(), key=lambda pair: pair[1])` vẫn **xử lý theo `email_normalized ASC`** (chống deadlock, prompt [6]).
- Dòng trả về đổi thành `[invited[key] for key in first_seen]` — **bắt buộc** phải đổi, vì `emails` nay còn trùng
  nên biểu thức cũ `[invited[keys[email]] for email in emails]` sẽ nhân bản phần tử. Kết quả: mỗi email duy nhất
  đúng một dòng, theo thứ tự xuất hiện đầu — vẫn là hợp đồng cũ.
- Vòng `_invite_one` chạy trên tập khoá duy nhất nên không có lượt `INSERT` lặp; `_require_none_taken` vẫn đọc từ
  `existing` của tập khoá duy nhất. Không mở đường đua mới.

Test mới `tests/test_invite.py:445-456` `test_users_invite_users_batch_cap_counts_before_dedupe`: trần 3, gửi 4 phần
tử mà bỏ trùng còn 2 → khẳng định `(422, "VALIDATION", "emails")`, **và** `_users_by_email(...) == []` (không tạo ai),
**và** `batches == []` (không thư). Assert thật. Bỏ bản sửa đi thì lô này trả 201 ⇒ test đỏ. **Finding 2 đóng.**

Bốn test cũ ràng buộc đường này vẫn xanh và vẫn đúng nghĩa sau khi đổi: `__C15` (1 / đúng trần / trần+1 phần tử
khác nhau), `default_batch_cap_is_50` (51 email **khác nhau** → 422), `dedupes_by_normalized_email`
(`["Ai@…","ai@…"]` → đúng một dòng `"Ai@…"`), `__C01` (thứ tự trả về `zeta, alpha` — cố tình nghịch alphabet nên
chốt được "trả theo thứ tự đầu vào, không theo thứ tự xử lý").

## Finding lượt 2

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | MNT-02 | Docstring **đầu module** còn câu "…(K37); bỏ trùng theo `normalize_email`, giữ thứ tự đầu (K20)", mô tả việc mà module này **không còn làm** — bỏ trùng đã chuyển sang `service.invite_users`. Docstring của chính lớp `InviteBody` (`:86`) và của `_validate_emails` (`:94`) **đã** được sửa đúng, chỉ header bị bỏ sót. `RULE.md` §1 xếp "comment" vào P3; **không** áp quy tắc nâng mức §1 vì đây là chú thích, không phải hành vi, không mang rủi ro vận hành | `apps/api/users/schemas.py:4-6` | Bỏ mệnh đề cuối, hoặc đổi thành "bỏ trùng và trần lô do `service.invite_users` làm" cho khớp docstring lớp |
| 2 | Nit | R-10 | `keys` là phép đảo thuần của `first_seen`, chỉ phục vụ hai chỗ mà cả hai viết thẳng từ `first_seen` được: `list(keys.values())` ≡ `list(first_seen)`, và `sorted(keys.items(), key=lambda pair: pair[1])` ≡ `sorted(first_seen.items())` (chỉ hoán vị thứ tự unpack; khoá duy nhất nên `sorted` không bao giờ chạm tie-break thứ hai). Mã hiện tại **đúng**, chỉ là thừa một dòng và một lambda | `apps/api/users/service.py:417-418` | `for key, email in sorted(first_seen.items()):` và `_lock_by_emails(db, list(first_seen))`; xoá dòng `keys = …` |
| 3 | Nit | TEST-04 | Biểu thức trả về của `invite_users` **bị viết lại** ở vòng này, nhưng thứ tự đầu ra chỉ được chốt bởi hai test rời: `__C01` (2 email, **không** trùng) và `dedupes_by_normalized_email` (2 email, **một** khoá duy nhất). Không test nào có đồng thời ≥ 2 khoá **và** một bản trùng. Rủi ro thấp (thứ tự chèn của `dict` là ngữ nghĩa ngôn ngữ, và độ phủ nhánh đã 100 %) | `apps/api/users/service.py:422`; `tests/test_invite.py:196-202` | Thêm một dòng vào test bỏ trùng đã có: `["z@…","A@…","a@…"]` → kỳ vọng `["z@…","A@…"]` |

Không có P0/P1/P2. Không có điều kiện dừng sớm nào của `/merge-review` §2. Diff **không** đụng gì ngoài hai
finding được giao — không có mở rộng phạm vi, không sửa test cũ, không chạm `DEBT.md`, `changes/B1-05.md`
hay bất kỳ module nào khác.

## Điểm (chỉ chấm diff `7587f46..1f99c7e`)

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 (finding 1 lượt 1 đã đóng, có test hồi quy) | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (finding 2 lượt 1 đã đóng) | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (finding 3 là Nit) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 (finding 1 lượt 2, P3) | 0,12 |
| **Tổng** | **100 %** | | **4,97 / 5** |

## PHÁN QUYẾT: APPROVE (4,97/5)

Vòng sửa làm **đúng** và **chỉ** hai việc được giao. Finding 1 (P2) đóng bằng đúng bản vá lượt 1 đề nghị,
kèm test hồi quy thật cho cả `U+212A` lẫn `U+017F` và khẳng định người không bị xoá. Finding 2 (P3) đóng với
**một** chỗ kiểm trần duy nhất đếm trên danh sách gốc; phần bỏ trùng chuyển xuống service được reviewer kiểm lại
là tương đương về tập khoá, thứ tự xử lý và thứ tự trả về. Bước 1–4 và bộ test + độ phủ của module do reviewer tự
chạy đều xanh (114 passed, `apps/api/users` 100 % dòng **và** 100 % nhánh), không số nào lệch với `gate2.log`.

**Được merge.** Ba mục còn lại đều không chặn và **không** cần dòng `DEBT.md` mới: finding 1 lượt 2 là một câu
docstring lệch mã, finding 2 và 3 là gợi ý. Tác giả có thể gộp cả ba vào một commit dọn nhỏ, hoặc bỏ qua.
`NO-206` và `NO-207` (finding 3, 4 của lượt 1) vẫn `⬜` đúng như đã ghi và **không** thuộc phạm vi lượt này.
