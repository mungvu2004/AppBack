# Review merge test/qa07-py → main — lượt 2

- Ngày: 2026-10-15 · Reviewer: phiên /merge-review · Commit đầu nhánh: e5fc6ad783d1 (merge-base = `main` e06c8607e654, `main` chưa đổi)
- Lượt 1: `docs/reviews/2026-10-15-test-qa07-py.md` (d1759df4) — REJECT dừng sớm: (1) thiếu changelog QA-07b / BUG-P07-014,
  (2) BUG-P07-015 không có dòng `DEBT.md`, (3) chưa có lượt cổng đầy đủ.
- Cổng: phạm vi **đầy đủ** — lượt đầy đủ đầu tiên của nhánh (R-33b đk 1), và `packages/core/text.py` là sàn cứng (đk 2), đổi
  hành vi tên công khai `clean_text`/`first_forbidden_char` (đk 4), thêm test mới (đk 3). `bash tools/verify/run.sh verify`
  mã thoát **0**, do người điều phối chạy dưới khoá stack 15:09–15:21Z (log: `F:/worktrees/AppBack/p07-py.full-gate.log`,
  log trong: `.cache/src-out/verify/20261015T150924Z-e5fc6ad783d1.log`). Reviewer **không chạy lại** (máy 24 GB, stack QA đang
  dùng) mà tự kiểm log: tên log trong mang sha `e5fc6ad783d1` = `git rev-parse HEAD`, cây sạch; bước 0–8 và 5b `đạt`,
  `8477 passed`, `coverage_gate: đạt`, `mã thoát: 0`.
- Độ phủ: tổng dòng 99,46% · nhánh 98,00% — `apps/api/me` 99,49%/98,53% · `packages/core` 100%/100% · tập file bị chạm
  98,94%/95,45% (từ log cổng trên).

## Phạm vi lượt 2

Diff `d1759df4..e5fc6ad7` (7 tệp, +66/−6):
- `d3ca3b42 docs(changes)` — `changes/QA-07.md` thêm mục BUG-P07-014, `changes/QA-07b.md` mới, `DEBT.md` NO-423 (BUG-P07-015).
- `e5fc6ad7 fix(me)` — quyết định người dùng Q4 phase 07 (`backend/dieu-phoi/chay/QA-07/timeline.md:43` "Q4 YES (BE rejects
  U+200B in fullName)"): `packages/core/text.py` thêm `_ZERO_WIDTH` + tham số `zero_width: bool = False` cho
  `first_forbidden_char`/`clean_text`; chỉ `UpdateMeBody.full_name` (`apps/api/me/schemas.py:52`) truyền `True`.

Điều kiện dừng sớm: cây sạch; `main` không đổi (merge-base = tip); hai commit mới đúng mẫu Conventional Commits, trailer
`Prompt: QA-07` đọc được (`%(trailers:key=Prompt)`); không chạm file cấm; không `pragma`/`type: ignore`/`noqa`/`skip`/`xfail`
mới trong `main...HEAD`. Diff toàn nhánh 14 tệp +415/−69, logic < 20 dòng → không MNT-05.

## Finding lượt 1 — trạng thái

| # lượt 1 | Trạng thái | Bằng chứng |
|---|---|---|
| 1 (changelog) | Đã đóng | `changes/QA-07.md` mục "BUG-P07-014" và "Q4, B07-C-071"; `changes/QA-07b.md` mô tả docstring catalog + B07-G-112; cả hai ghi bước 6–8 không có gì mới — đúng, không route/bảng/migration/dây mới. |
| 2 (DEBT BUG-P07-015) | Đã đóng (còn thiếu ô mức — finding 2 dưới) | `DEBT.md` NO-423. |
| Cổng đầy đủ | Đã đóng | Log trên, mã thoát 0 tại HEAD. |

## Kiểm độc lập (tĩnh) phần Q4

- `first_forbidden_char`: `blocked = _BIDI_OVERRIDE` rồi `blocked |= …` trên `frozenset` tạo tập mới, không sửa hằng mô-đun;
  mặc định `zero_width=False` → mọi nơi gọi khác (`auth_recovery/router.py:66`, `drawings`, `floors`, `measurements`,
  `project_settings`, `versions/service.py:306`, `domain/spatial/model.py:62`, hai trường khác của `me/schemas.py`) giữ hành vi
  cũ — kiểm bằng `grep clean_text(\|first_forbidden_char(` toàn `apps packages`.
- Biên: `str.strip()` không bỏ U+200B/U+FEFF (không phải khoảng trắng Python), NFC không xoá chúng → ký tự vô hình ở đầu/cuối
  cũng bị chặn; thông báo lỗi nêu điểm mã như luật Cc.
- Dây: vẫn 422 `VALIDATION` `field:"fullName"` (test khẳng định `code`, `field`, và DB không đổi). `HOP-DONG-MOI.md:285,294`
  chỉ nêu "trim, 1–120" cho `fullName`; luật Cc/bidi vốn đã ngoài hiến chương → không phải breaking change hợp đồng; FE gửi
  chỉ các khoá đổi (`accountSettingsGateway.ts:54-61`) nên người dùng có tên cũ chứa U+200B không bị khoá khi sửa trường khác.
- Test: `test_clean_text__zero_width_only_when_asked` (5 ký tự × mặc định lọt / `True` chặn) và
  `test_me_update_profile_full_name_zero_width_char_is_422` (API thật + DB thật, K23). Đỏ trước sửa
  `p07-py.q4-red.log` "10 failed", xanh `p07-py.q4-pytest.log` "482 passed", cổng đầy đủ xanh.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|-----|----|-------|--------|---------|
| 1 | P3 | LOG / R-19 | Luật Q4 chỉ áp cho N12. N10 nhận lời mời ghi **cùng cột** `users.name` từ **cùng trường dây** `fullName` qua `_validate_full_name` → `clean_text(value)` mặc định, nên người được mời vẫn đặt được tên `"Nguyễn\u200bVăn"`; sau đó PATCH chỉ từ chối nếu gửi lại `fullName`. Quyết định người dùng nói "BE rejects U+200B in fullName", không giới hạn ở `/api/me`. Không thuộc sở hữu nhánh này (R-27, `apps/api/auth_recovery`). | `apps/api/auth_recovery/router.py:64-68,98-102` | Ghi một dòng `DEBT.md` **trước merge** (R-38; được commit thẳng `main` theo ngoại lệ R-36): `_validate_full_name` truyền `zero_width=True` + test N10 tham số 5 ký tự, gộp cùng đợt sửa NO-423 (cùng tệp, cùng chủ). |
| 2 | P3 | R-34 | Dòng NO-423 dồn mọi thứ vào một ô, thiếu ô **mức** và **chủ sở hữu** tường minh (BUG-LOG-P07 ghi BUG-P07-015 Security/Low). | `DEBT.md:443` | Bổ sung "P3, chủ `apps/api/auth_recovery` (B1-03)" vào dòng khi thêm dòng của finding 1. |
| 3 | Nit | MNT | `questions.md` bảng Q4 vẫn ghi mặc định "Không — không đổi dây N12"; câu trả lời "YES" chỉ có ở `timeline.md:43`, trong khi trailer commit ghi `Bug: Q4 phase 07`. Ngoài nhánh. | `backend/dieu-phoi/chay/QA-07/questions.md:8` | Người điều phối ghi "Người dùng: CÓ (14:46Z)" vào dòng Q4. |
| 4 | Nit | — | Câu lỗi FE "không chứa ký tự điều khiển" chưa nhắc ký tự vô hình. Ngoài phạm vi AppBack. | AppFront `src/screens/account/AccountSettings/useAccountSettings.ts:113` | Tuỳ FE. |

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |

Tổng: 4,82 / 5

## PHÁN QUYẾT: APPROVE

Ba điều chặn của lượt 1 đã đóng có bằng chứng; thay đổi Q4 tối thiểu, opt-in, không đổi hành vi nơi gọi khác, có test đỏ→xanh
đúng tầng; cổng đầy đủ mã thoát 0 tại đúng HEAD e5fc6ad7, độ phủ ≥ 90/90. Không P0/P1/P2. Điều kiện khi merge (R-38): thêm
dòng `DEBT.md` cho finding 1 và bổ sung mức/chủ cho NO-423 (finding 2) — nhật ký quản trị, commit thẳng `main` được. Nhánh
mang hai mã `Prompt:` (QA-07, QA-07b) → gộp `--no-ff`, không squash (R-36). Cây sau gộp trùng cây
đã qua cổng đầy đủ (base không đổi) → không cần verify tích hợp lại, trừ khi `main` đổi trước lúc gộp.
