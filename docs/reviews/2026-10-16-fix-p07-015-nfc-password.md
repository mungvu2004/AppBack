# Review merge fix/p07-015-nfc-password → main

- Ngày: 2026-10-16 · Reviewer: phiên /merge-review · Commit đầu nhánh: 6671b30da92e (merge-base = `origin/main` bd1e8bb76050)
- Cổng: phạm vi đầy đủ — lượt 1 của nhánh (R-33b đk 1; diff còn chạm đk 4: `apps/api/auth/passwords.py` là module công khai mà
  `auth`, `auth_recovery`, `me` nhập). `bash tools/verify/run.sh verify` **mã thoát 0** (log: `.cache/src-out/verify/20261016T111840Z-6671b30da92e.log`, bản ngoài `F:/worktrees/AppBack/_logs/debt-p07-015.verify.log`; reviewer tự chạy 11:18Z dưới stack-lock, f14 dừng). Bước 0–8 đều `đạt`; pytest `8508 passed`; perf 1 test.
- Độ phủ: tổng dòng 99,47% · nhánh 98,02% — `apps/api/auth` dòng 99,77% · nhánh 97,76% — `apps/api/auth_recovery` dòng 99,76% · nhánh 94,44% — tập file bị chạm dòng 100,00% · nhánh 100,00%.

## Phạm vi

1 commit `fix(auth_recovery): NFC before min length on N9/N10 new password`, 6 file, +39/−5:
`apps/api/auth/passwords.py` (+10/−1: `_nfc_if_str`, kiểu `NewPassword`), `apps/api/auth_recovery/router.py` (+3/−3: N9
`new_password`, N10 `password` dùng `NewPassword`), hai test mới `__C02_nfd_length`, `changes/DEBT-P07.md` (mới), `DEBT.md` (NO-423 ✅).

Điều kiện dừng sớm (§2): không có. Cây sạch; `changes/DEBT-P07.md` có; dòng đầu đúng Conventional Commits; khối trailer
`Prompt: DEBT-P07` / `Bug: BUG-P07-015` / `Co-Authored-By` liền nhau (`%(trailers:key=Prompt,valueonly)` → `DEBT-P07`); không chạm
`docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`; không `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới.

## Kiểm tính đúng của bản sửa

- Gốc lỗi: N9/N10 khai `Annotated[str, Field(min_length=8)]` → Pydantic đếm điểm mã của chuỗi thô, còn `hash_password` băm
  `nfc(password)` (`passwords.py:132`). `"ê"*4` = 8 điểm mã NFD lọt trần, lưu thành mật khẩu NFC 4 ký tự.
- Mã mới: `NewPassword = Annotated[str, BeforeValidator(_nfc_if_str), Field(min_length=MIN_PASSWORD_LENGTH)]` (`passwords.py:39-44`).
  `BeforeValidator` chạy trước ràng buộc `min_length` của `str` → đếm sau NFC. Giá trị không phải `str` đi tiếp và bị `str` strict
  của `WireRequest` từ chối như cũ. `hash_password` NFC lần nữa — idempotent, không đổi băm của mật khẩu cũ.
- Schema OpenAPI không đổi (`BeforeValidator` không vào JSON schema; vẫn `type:string, minLength:8`), mã lỗi vẫn 422 `VALIDATION`,
  trường lỗi theo alias (`newPassword`, `password`) — bước 8 của cổng kiểm.
- Các đường khác dùng `MIN_PASSWORD_LENGTH` (R-19): N13 `apps/api/me/schemas.py:103-109` đã có validator `mode="before"` riêng
  (BUG-P07-014) — đúng nhưng trùng lặp (finding 2); CLI `apps/api/auth/cli.py:112` đếm `len(nfc(password))` — đúng; đăng nhập
  `apps/api/auth/router.py:72` không phải mật khẩu mới (chỉ để so băm) — không cần.
- Test mới: chuỗi trong tệp là byte `65 CC 82` ×4 (đã kiểm bằng `od -c`) → đúng NFD; trên `main` (thô 8 ≥ 8) thân qua kiểm, test đỏ;
  sau sửa 422 đúng trường. Đỏ-trước-sửa: log tác giả `F:/worktrees/AppBack/_logs/p07-015-red.log` (`2 failed, 9 passed`, đúng 2 test
  mới), xanh `p07-015-green.log` (`343 passed`); reviewer không tự chạy lại phía đỏ (máy giữ một việc nặng), xanh được cổng đầy đủ xác nhận.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | TEST | Ký tự NFD viết trực tiếp `"ê"` (byte `e` + U+0302) — mắt thường không phân biệt với `"ê"` NFC. Một trình soạn thảo/công cụ chuẩn hoá NFC khi lưu sẽ đổi thành 4 điểm mã: test vẫn xanh (4 < 8 ở cả mã cũ) nhưng mất hoàn toàn khả năng bắt hồi quy BUG-P07-015, không ai thấy | `apps/api/auth_recovery/tests/test_router_confirm_reset.py:63`, `test_router_accept_invitation.py:66` | Viết tường minh `"ê" * 4` (hoặc `unicodedata.normalize("NFD", "ê") * 4`) và/hoặc `assert len(pw) == 8` trong test |
| 2 | P3 | R-07 | Logic `nfc(value) if isinstance(value, str) else value` nay có **hai** bản: `_nfc_if_str` mới và `ChangePasswordBody._nfc_before_length` (N13). Docstring `NewPassword` ghi "(N9, N10, N13)" nhưng N13 **không** dùng `NewPassword` → docstring sai sự thật. `DEBT.md` NO-423 ghi "N13 giữ validator riêng" nhưng không mở dòng nợ cho phần còn lại (R-34) | `apps/api/auth/passwords.py:39-44`; `apps/api/me/schemas.py:103-109`; `DEBT.md:443` | Mở một dòng `NO-` (P3, chủ `apps/api/me`): `ChangePasswordBody.new_password: NewPassword`, xoá `_nfc_before_length`; tới khi đó sửa docstring `NewPassword` thành "(N9, N10; N13 còn validator riêng — NO-xxx)" |
| 3 | Nit | R-01 | Hàm mới `_nfc_if_str` không có docstring (R-01: mỗi hàm, kể cả hàm một dòng, một câu) | `apps/api/auth/passwords.py:39-40` | Một câu: vì sao bỏ qua giá trị không phải `str` (để `str` strict của Pydantic ra 422 đúng kiểu thay vì `TypeError` trong `nfc`) |
| 4 | Nit | R-34 | Dòng NO-423 sau sửa có **10** ô thay vì 9 (`| Thấp || DEBT-P07 …`: thêm một ô rỗng) — các dòng khác (NO-422, NO-426) 9 ô; bảng hiển thị lệch cột | `DEBT.md:443` | Đổi `| Thấp || DEBT-P07` thành `| Thấp | DEBT-P07` |

Không có P0/P1/P2.

## Kiểm sổ nợ

- NO-423 (Thấp) đóng ✅ với bản sửa + 2 test — đúng R-34, trừ phần N13 chưa có dòng mở (finding 2).
- Không nợ P0/P1 mở mới nào liên quan nhánh.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |

Tổng: 4,90 / 5

## PHÁN QUYẾT: APPROVE
Sửa đúng gốc ở một kiểu dùng chung cạnh `MIN_PASSWORD_LENGTH`, N9 và N10 cùng đi qua; dây và OpenAPI không đổi; có test hồi quy đỏ → xanh; cổng đầy đủ tại đúng sha đầu nhánh thoát 0 (8508 test, độ phủ 99,47/98,02, file chạm 100/100). Không P0/P1/P2; hai P3 và hai Nit không chặn. Nên làm khi gộp (squash, giữ khối trailer `Prompt: DEBT-P07`): sửa ô thừa NO-423 (#4) và docstring `NewPassword` (#2); mở dòng nợ N13 dùng `NewPassword` (#2); #1 và #3 đi đợt DEBT kế tiếp hoặc cùng lúc. Base không đổi so với `origin/main` bd1e8bb7 lúc review — `main` đổi trước khi gộp thì chạy lại cổng trên cây tích hợp.
