# Review merge fix/qa02b-be-notify-caps → main

- Ngày: 2026-10-11 · Reviewer: phiên /merge-review · Commit đầu nhánh: 63caba9766ed (base `main` 8fa5db3833c9, `main` chưa đi tiếp)
- Cổng: phạm vi đầy đủ — lượt 1 của nhánh (R-33b đk 1), diff chạm `packages/testing/**` (đk 2); `bash tools/verify/run.sh verify` mã thoát 0
  (log: `F:/App/AppBack/backend/dieu-phoi/chay/QA-02b/verify-be-1.log`, dòng 1 trỏ log gốc
  `.cache/src-out/verify/20261011T120153Z-63caba9766ed.log` — sha trong tên trùng HEAD; bước 0–8 `đạt`, 8428 passed, `verify exit=0`)
- Độ phủ: tổng dòng 99,47% · nhánh 98,02% — `apps/api/notifications` 100%/100%, `packages/testing` 99,54%/98,45%, tập file bị chạm 100%/100%

## Phạm vi

1 commit `fix(notifications): capitalize fixed notification sentences (A6)`, trailer `Prompt: QA-02b` đọc được (R-36b).
9 file, +34/−19: ba câu cố định trong `apps/api/notifications/messages.py` viết hoa chữ đầu; test, `tests/support.py` và
factory `packages/testing/factories/notifications.py` đổi theo; thêm `test_messages__fixed_sentences_start_uppercase`;
`changes/QA-02b.md` có. Không route, không bảng, không migration, không đổi hình dạng dây.

Điều kiện dừng sớm: cây sạch; `changes/QA-02b.md` có; dòng đầu đúng Conventional Commits; không file cấm; không
`pragma`/`type: ignore`/`noqa`/`skip`/`xfail` mới → không áp dụng.

R-19 (mọi caller): `git grep` — `project_invite` gọi từ `invite_sinks.py`, `ai_completed` từ
`apps/worker/pipeline_persist/service.py`; cả hai đi qua `messages.py` nên sửa ở gốc là đủ. Không còn chuỗi viết thường
nào trong `apps/`, `packages/` (`packages/testing/fixtures/streams.py:343` là câu khác, đã viết hoa sẵn).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG-06 | Bảng câu gốc ở `backend/prompts/B4-02.md:138-140` vẫn ghi câu viết thường, còn docstring test vẫn nói "Đúng bảng [6]" — nay test khẳng định câu viết hoa, lệch bảng đó; `changes/QA-02b.md` không ghi "Lệch khỏi prompt B4-02 [6]". | `apps/api/notifications/tests/test_messages.py:23`; `changes/QA-02b.md` | Ghi một dòng "lệch B4-02 [6] theo luật chữ A6 (ND-C5)" vào `changes/QA-02b.md` hoặc docstring test; không chặn. |
| 2 | P3 | API-04 | Phía AppFront còn chép câu cũ: mock `src/api/__mocks__/client.ts:1031,1043,1079`, regex e2e `e2e/v2v3/notification-center.spec.ts:152`, nhánh thứ hai của regex QA `qa/tests/phase02_dashboard_api.spec.ts:976` (kiểm trên master, `fix/qa02b-int`, `fix/qa02b-master`). Hiện không hỏng (e2e chạy trên mock; test API đi nhánh có tên), nhưng mock lệch dây thật và nhánh `bạn vừa…` của regex thành chết. | AppFront (ngoài nhánh này) | Chủ AppFront đổi mock + regex theo câu mới trong đợt QA-02b FE, hoặc ghi một dòng `DEBT.md` (R-38) trước khi gộp. |
| 3 | Nit | OPS-03 | Dòng thông báo đã lưu giữ câu viết thường → hộp thư có thể lẫn hai kiểu chữ đến khi dòng cũ bị dọn. Đã ghi ở `changes/QA-02b.md:8`; chỉ là chữ hiển thị, rollback an toàn. | `changes/QA-02b.md:8` | Chấp nhận như đã ghi. |

Ngoài phạm vi diff (nợ có sẵn, chuyển đợt DEBT sau): `messages.violation_found` không có caller sản phẩm nào
(`git grep violation_found -- apps packages` chỉ ra định nghĩa và test) — hoặc chờ prompt sinh `violationFound`, hoặc mã chết (R-11).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 4 | 0,40 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 5 | 0,15 |

Tổng: 4,75 / 5

## PHÁN QUYẾT: APPROVE
Không P0/P1/P2; điểm 4,75 ≥ 4,0. Sửa đúng gốc (một module mọi đường gọi đi qua), có test chặn hồi quy, cổng đầy đủ
mã thoát 0 trên đúng HEAD 63caba9766ed, độ phủ 100/100 trên file chạm. Hai P3 không chặn; finding 2 nên được đóng ở
AppFront hoặc ghi `DEBT.md` trước khi gộp (R-38).
