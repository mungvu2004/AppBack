# Review merge fix/vectorize-hang → main

- Ngày: 2026-10-16 · Reviewer: phiên /merge-review · Commit đầu nhánh: 6971f19eaab3 (merge-base = `main` 3155dd5454de, base không đổi)
- Cổng: phạm vi đầy đủ — lượt 1 của nhánh (R-33b đk 1). `bash tools/verify/run.sh verify` **mã thoát 0**
  (log: `.cache/src-out/verify/20261016T025256Z-6971f19eaab3.log`, chạy 02:52Z sau commit 02:39Z, tên log mang đúng sha đầu nhánh).
  Bước 0–8 đều `đạt`; junit `tests="8478" failures="0" errors="0" skipped="0"`; perf 3 test.
  Reviewer **đọc log và junit**, không chạy lại: lượt đầy đủ ~25 phút vượt hạn 20 phút của phiên, và đang có cổng của phiên khác
  (`appback-verify-p08-py-…`) chiếm máy — CLAUDE.md: một việc nặng mỗi lúc.
- Độ phủ: tổng dòng 99,47% · nhánh 98,02% — `packages/vision` dòng 99,72% · nhánh 99,05% — tập file bị chạm dòng 98,90% · nhánh 97,22% (log dòng 378–381).

## Phạm vi

1 commit `fix(vision): stop vectorize hanging on self-looping short segments`, 4 file, +60/−2:
`packages/vision/walls/vectorize.py` (`_drop_short`, +5/−1), `packages/vision/walls/tests/test_vectorize.py` (+42),
`changes/PERF-02.md` (mới), `DEBT.md` (NO-425 đóng, NO-426 mở P3).

Điều kiện dừng sớm (§2): không có. Cây sạch; `changes/PERF-02.md` có; dòng đầu đúng Conventional Commits; không chạm
`docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`; không `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới.
Trailer `Prompt: PERF-02` có trong thân nhưng tách đoạn khỏi `Co-Authored-By` → `%(trailers:key=Prompt)` rỗng: Nit #1
theo tiền lệ review B0-08 #11 (nhánh một prompt, gộp squash với khối trailer đúng).

## Kiểm tính đúng của bản sửa

- Mã cũ: `alias[seg.b_key] = seg.a_key`. Đoạn có `a_key == b_key` ghi `alias[k] = k` → `_resolve` (`while key in alias`) quay mãi
  khi đoạn giữ lại dùng `k`; ba đoạn ngắn khép vòng (a–b, b–c, c–a) cũng cho chu trình. Đọc mã xác nhận đúng gốc như báo cáo.
- Mã mới (`vectorize.py:480-482`): `head`, `tail` là gốc (không nằm trong `alias`), chỉ ghi `alias[tail] = head` khi `head != tail`.
  Mọi lần ghi nối một gốc vào một gốc khác → `alias` là rừng, không bao giờ có chu trình; `_resolve` luôn dừng. Sửa ở hàm chung,
  mọi đường gọi (`vectorize`, `vectorize_with_stats`, `segment_page`) đều đi qua dòng 605 → sửa gốc (R-19).
- Test mới: hạn 10 s trong luồng nền daemon, nên lỗi cũ làm test đỏ chứ không treo cổng; xanh ở HEAD (junit 0,012 s).
  Đỏ-trước-sửa: reviewer **không tự tái hiện** (máy chủ không có `cv2`, container verify đang thuộc phiên khác); bằng chứng là
  báo cáo tác giả (hết hạn 10 s trong container verify) cộng lập luận ở trên.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | R-36b | `Prompt: PERF-02` và `Co-Authored-By` cách nhau một dòng trống → `git log -1 --format='%(trailers:key=Prompt,valueonly)'` in rỗng | thân commit `6971f19e` | Gộp **squash** (một prompt, R-36), thân commit squash có khối trailer liền nhau `Prompt: PERF-02` + `Co-Authored-By`, kiểm lại bằng lệnh trên sau khi gộp |
| 2 | Nit | LOG | Ngoài ca treo, hành vi đổi cả ở chuỗi đoạn ngắn: trước đây `alias[b]` bị **ghi đè** khi `b` đã có alias (mất một lần nhập), nay hai nhóm được nhập trọn. Đây là đúng ý docstring ("nhập hai khoá làm một") và cổng 8478 test xanh, nhưng `changes/PERF-02.md` không nêu | `vectorize.py:480-482` | Thêm một câu vào `changes/PERF-02.md` (hoặc thân commit squash) để người đọc lịch sử biết đầu ra có thể đổi trên trang có chuỗi đoạn vát góc |
| 3 | Nit | TEST | Docstring nói sửa cả "vài đoạn ngắn khép vòng" nhưng test chỉ phủ ca `a_key == b_key`; ca a–b, b–c, c–a không có test riêng | `test_vectorize.py:300-312` | Khi chạm lại module: test đơn vị `_drop_short` với ba `_Seg` ngắn khép vòng + một đoạn giữ lại dùng chung khoá, khẳng định trả về và hai đầu đoạn giữ lại cùng gốc |
| 4 | Nit | R-34 | Dòng NO-426 trỏ `vectorize.py:593,337`; sau sửa `distanceTransform` ở dòng **598**, `approxPolyDP` ở **338** (593 là số dòng trên `main`) | `DEBT.md` NO-426 | Đổi thành `:598,338` khi gộp hoặc khi đợt DEBT xử lý NO-426 |

Không có P0/P1/P2/P3. Hiệu năng: `_resolve` không nén đường, nhưng mỗi trang chỉ vài trăm khoá và A1f đo max 0,91 s → không phải finding.

## Kiểm sổ nợ

- NO-425 (P1, treo vô hạn) đóng ✅ với bản sửa + test đỏ → xanh — đúng R-34.
- NO-426 (P3, mặt nạ toàn `True` làm `approxPolyDP` ném lỗi) mở, có chủ (B5-02), nguyên nhân và hướng sửa; ngoài phạm vi nhánh,
  mức P3 không chặn merge (R-38 chỉ chặn P0/P1), đi đợt DEBT kế tiếp theo luật phạm vi.

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
| MNT | 3% | 5 | 0,15 |

Tổng: 5,00 / 5 (chỉ Nit, không trừ điểm)

## PHÁN QUYẾT: APPROVE

Bản sửa đúng gốc, nhỏ (6 dòng logic), làm `alias` thành rừng nên `_resolve` luôn dừng; có test hồi quy chặn treo bằng hạn 10 s;
cổng đầy đủ ở đúng sha đầu nhánh thoát 0 (8478 test, độ phủ 99,47/98,02). Bốn Nit không chặn. Điều kiện khi gộp:
**squash** với khối trailer `Prompt: PERF-02` đọc được (Nit #1); nên kèm sửa Nit #2 (một câu) và #4 (số dòng) trong cùng lúc gộp.
Cây sau gộp trùng cây đã qua lượt đầy đủ (base không đổi) → không cần verify tích hợp lại, trừ khi `main` đổi trước lúc gộp.

## Ghi chú sau review (2026-10-16, phiên tác giả)

`main` đổi trước lúc gộp (3aca5a30, QA-08) và QA-08 đã dùng NO-425: nợ của nhánh này đánh số lại — treo vô hạn **NO-426** (đóng),
mặt nạ toàn `True` **NO-427** (mở P3). Đã gộp `main` vào nhánh và chạy lại cổng đầy đủ trên cây tích hợp trước khi squash.
