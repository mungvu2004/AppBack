# Review merge merge/ghep-master → master (AppFront) — GHEP-MASTER, lượt 2

- Ngày: 2026-10-06 · Reviewer: phiên /merge-review riêng (R-37), không phải tác giả · Lượt 1: `docs/reviews/2026-10-06-merge-ghep-master.md` (`81ad9154`, APPROVE WITH COMMENTS)
- Commit đầu nhánh: `5bf3a9eefc8b` (cây sạch, `git status --porcelain` rỗng). Vòng sửa soát: `81ad9154..5bf3a9ee` = `1b5ca43e` (FIX-383) + `5bf3a9ee` (FIX-384); 2 tệp, +53/−46.
- Cổng: phạm vi **đích** (R-33b) — vòng sửa chỉ bỏ một khối hook nội bộ trong `src/screens/system/EditorTour/useEditorTour.ts` (không đổi kiểu/tên xuất khẩu, `EditorTourProps` chỉ đổi chú thích) và thêm một khối test; không tệp mới, không đổi lock/schema/cấu hình. Log tác giả (mỗi log in `sha=`/`porcelain=` ở đầu): `round2-typecheck.log` EXIT 0, `round2-lint.log` EXIT 0, `round2-length.log` EXIT 0 (0 tệp > 400), `round2-vitest.log` sha `5bf3a9ee` porcelain 0 — 9 tệp / 176 test EXIT 0, `round2-e2e.log` sha `5bf3a9ee` — `editor-tour-chip.spec.ts` + `viewer3d.spec.ts` 20/20 EXIT 0. Reviewer tái hiện tại chỗ trên `5bf3a9ee`: `pnpm exec vitest run EditorTour.test.tsx useProcessingScreen.test.ts processingGateway.test.ts` → 3 tệp / 77 test, EXIT 0.
- Độ phủ: không đo (phạm vi đích). Lượt đầy đủ gần nhất: `verify-1.log` trên `cbfdbaae` (7/7 EXIT 0).

## Soát finding lượt 1
| # lượt 1 | Trạng thái | Bằng chứng |
|---|---|---|
| 1 P2 (e2e đỏ, NO-381/382) | Chuyển DEBT-03 (X1/X2) — **giữ làm điều kiện merge (b)**. Dòng NO-381 trong `DEBT.md` đã thêm đính chính bằng chứng. | `DEBT.md:401` |
| 2 P2 (hai cơ chế dò neo) | **Đóng.** `1b5ca43e` xoá trọn khối `useEffect` + MutationObserver + rAF + `setAnchorTick` của master (`eae963a9`), giữ `subscribeDom` + `useSyncExternalStore` (`useEditorTour.ts:448-461,514-518`). Còn đúng một `new MutationObserver` trong tệp. Hành vi NO-208 không mất: bài master "NO-208 — neo có mặt SAU commit đầu" vẫn xanh (tái hiện tại chỗ), và đột biến tắt `subscribeDom` làm chính bài ấy đỏ (`fix383-mutation-subscribeDom.log`, sha `81ad9154` + đột biến, EXIT 1) ⇒ cơ chế còn lại là thứ bài đó chặn. Bài B-V2-01 của integrate cũng xanh. | diff `81ad9154..1b5ca43e` |
| 3 P3 (dòng `refreshAuth` không test nào bắt) | **Đóng.** Bài mới "processingGateway — NO-154 qua cổng tiến độ" (`useProcessingScreen.test.ts:1242-1281`) đi qua `createProcessingGateway(...).subscribeProgress` thật với `MockEventSource`: SSE chết `SSE_FAILURE_LIMIT` lần ⇒ `refreshSingleFlight` gọi đúng 1 lần với `{ source: 'local' }`; thử lại SSE rồi chết tiếp ⇒ vẫn 1 lần (chốt "một lần mỗi chuỗi chết"). Đột biến xoá dòng `processingGateway.ts:826` ⇒ bài đỏ "called 0 times" (`fix384-mutation-red.log`, EXIT 1); khôi phục ⇒ 27/27 xanh. | diff `1b5ca43e..5bf3a9ee` |
| 4 P3 (chú thích mặc định chip) | **Đóng.** `useEditorTour.ts:122-125` nay ghi "Mặc định giữa cạnh dưới (B-V2-05) — xem `DEFAULT_CHIP_ANCHOR`". | diff `81ad9154..1b5ca43e` |
| 5 Nit (log không in sha) | **Đóng.** Mọi log round 2 in `sha=` + `porcelain=` ở dòng đầu. | `round2-*.log`, `fix38[34]-*.log` |

`xung-dot.md` thêm 2 dòng (27, 28) cho hai xung đột ngữ nghĩa này, đủ cột, có test chứng minh.

## Finding mới
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | TEST | `vi.mock('@/lib/auth', …)` áp cho **cả tệp** `useProcessingScreen.test.ts`, không chỉ khối NO-154: mọi bài cũ trong tệp làm SSE chết nay gặp `refreshSingleFlight` giả trả `false` thay vì bản thật. Không làm bài nào yếu đi (bài cũ không khẳng định gì về refresh, và bản giả tránh một lượt refresh thật đi qua cấu hình auth trong test) — chỉ là phạm vi giả rộng hơn cần. | `src/screens/pipeline/ProcessingScreen/useProcessingScreen.test.ts:51-55` | Không bắt buộc. Nếu muốn chặt: `vi.spyOn` trong `beforeEach` của khối NO-154. |

Không `skip/fixme/eslint-disable/@ts-*` mới trong vòng sửa; không đổi `src/lib/schemas`; không assert nào bị nới.

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

Tổng: 5,00 / 5 (NO-381/382 chấm ở DEBT-03, không chấm vào nhánh gộp — theo chỉ đạo điều phối)

## PHÁN QUYẾT: APPROVE
Nội dung nhánh `merge/ghep-master` @ `5bf3a9eefc8b` được duyệt: finding 2–5 của lượt 1 đã đóng có bằng chứng đột biến, NO-208 giữ hành vi, NO-154 nay có test đi qua cổng. **Điều kiện trước khi gộp vào `master` (mang từ lượt 1, thuộc DEBT-03/điều phối, không chặn phán quyết nội dung):** (b) `pnpm e2e` 0 hỏng, bỏ qua ≤ 16 trên cây cuối (sau X1/X2 — NO-381, NO-382); (c) chuỗi thật F-14 `chuoi-1.log` xanh trên cây cuối; (d) commit nào thêm vào nhánh sau `5bf3a9ee` phải qua review đích lượt 3; (e) R-33b "verify tích hợp": nhánh đã có vòng sửa kiểm đích sau lượt đầy đủ `cbfdbaae`, nên `pnpm verify` đầy đủ phải chạy một lần trên cây cuối (trước hoặc ngay sau gộp).
