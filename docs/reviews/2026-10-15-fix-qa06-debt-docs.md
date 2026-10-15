# Review merge fix/qa06-debt-docs → main

- Ngày: 2026-10-15 · Reviewer: phiên /merge-review · Commit đầu nhánh: ed94b15338a0 (base `main` b58555f90 = merge-base)
- Cổng: phạm vi đầy đủ — lượt 1 của nhánh (R-33b đk 1). Ghi chú: ngoài đk 1 thì diff chỉ đủ cho "đích" (so với lượt đầy đủ gần nhất
  `91a35685`, `main` chỉ thêm `docs/reviews/*`; nhánh chạm `apps/api/versions/**` sở hữu + `changes/`, không thêm/đổi tên `.py`,
  không đổi tên công khai, route hay tên test). `bash tools/verify/run.sh verify` (qua `stack-lock.mjs`, f14 dừng) **mã thoát 0**
  (log bọc: `F:/worktrees/AppBack/p06-debt-docs.verify-full.log` kết thúc `EXIT=0`; log cổng:
  `.cache/src-out/verify/20261015T120110Z-ed94b15338a0.log`). Bước 0–8 (gồm 5b) đều `đạt`; pytest `8465 passed`.
- Độ phủ: tổng dòng 99,46% · nhánh 97,98% — `apps/api/versions` 100%/100%; tập file bị chạm 100%/100%.

## Phạm vi

1 commit `ed94b153 docs(versions): …` — dòng đầu đúng Conventional Commits; khối trailer `Prompt: QA-06b` / `Bug: BUG-721` /
`Co-Authored-By` liền nhau, có dòng trống trước; `git log -1 --format='%(trailers:key=Prompt,valueonly)'` in `QA-06b` (R-36b đạt).
3 tệp, +12/−7: docstring `normalize_label`, một literal test, `changes/QA-06b.md`. Không đổi hành vi.

Điều kiện dừng sớm: cây sạch; `changes/QA-06b.md` có; không file cấm; không `pragma`/`type: ignore`/`noqa`/`skip`/`xfail` mới
(quét dòng `+`) → không áp dụng.

## Kiểm độc lập

- **Finding 5 (lượt 2 của `2026-10-15-fix-qa06-be.md`):** docstring mới khớp mã: `normalize_label` gọi
  `first_forbidden_char(text, bidi_marks=True)`; hàm này chặn `Cc` + `_BIDI_OVERRIDE` (U+202A–202E, U+2066–2069) + `_BIDI_MARKS`
  (byte `e2 80 8e`, `e2 80 8f` = U+200E, U+200F) — `packages/core/text.py:6-31`. ZWJ/U+200B không thuộc tập chặn → đóng.
- **Finding 6:** danh sách trong `changes/QA-06b.md` khớp đúng tập trên, ghi U+061C không chặn; năm tên test được nêu đều tồn tại
  (`apps/api/core/tests/test_errors.py:55,199`, `apps/api/versions/tests/test_routes_label.py:94,103`,
  `apps/api/rules/tests/test_rejections.py:41`) → đóng.
- **Finding 7:** `test_schemas.py:119` giờ là `("x\u200by", "x\u200by")`; quét byte U+200B–200F, U+202A–202E, U+2066–2069 thô trong ba
  tệp đổi: không còn → đóng.
- **Sổ nợ:** nhánh không đổi `DEBT.md`; báo cáo không nêu nợ mới → R-34/R-35 không áp dụng.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | MNT-04 | Ghi "khớp FE (`versionHistoryModel.ts:452`, `humanText.ts:19`)", nhưng `FORBIDDEN` của `humanText.ts:19` (AppFront `qa/phase06-run`) là `[\u0000-\u001F\u007F-\u009F\u202A-\u202E\u2066-\u2069]` — **không** có U+200E/U+200F mà BE chặn; luồng nhãn FE cũng không gọi `normalizeHumanText`, chỉ ánh 422 sang câu `LABEL_BAD_CHARS`. Tác động: chỉ tài liệu, người đọc tưởng hai tập trùng nhau. | `changes/QA-06b.md:10` | Bỏ tham chiếu `humanText.ts:19`, hoặc ghi "BE chặn thêm LRM/RLM so với `humanText.ts`; FE nhãn chỉ hiện lỗi máy chủ". |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |

Tổng: 4,97 / 5

P0: 0 | P1: 0 | P2: 0 | P3: 0 | Nit: 1

## PHÁN QUYẾT: APPROVE
Cổng đầy đủ thoát 0 trên `ed94b153`, độ phủ ≥ 90/90; ba finding 5–7 của review `fix/qa06-be` lượt 2 đã đóng đúng đề xuất, không đổi
hành vi. Finding 1 là Nit tài liệu, không chặn. Verify tích hợp trên `main` sau gộp bỏ được nếu cây sau gộp trùng cây `ed94b153`
(khác chỉ ở `docs/reviews/*`, `DEBT.md`).
