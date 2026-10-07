# Review merge fix/debt-03-fe-master → master (AppFront) — DEBT-03, lượt 3

- Ngày: 2026-10-07 · Reviewer: phiên /merge-review riêng (R-37), không phải tác giả.
- Lượt trước:
  - lượt 1: `2026-10-07-fix-debt-03-fe-master.md` (`c2731a75`);
  - lượt 2: `…-round-2.md` (`3b7c4b97`).
- Commit đầu nhánh: `1133a931` (merge R3 U), cây sạch (porcelain 0).
- Vòng soát: `3b7c4b97..1133a931`, gồm hai phần:
  - **Nit lượt 2:** `3b7c4b97..2d76371d`, 7 commit FIX-454…458, 13 tệp, +99/−43.
  - **Phương án B cho P3-4** (người dùng chọn): `fix/debt-03-w3-x1` `2d76371d..6ee43ecf`, tức `5cf238c4` (FIX-459) và `6ee43ecf` (FIX-460), 5 tệp, +413/−80. Merge `1133a931` không đổi thêm gì: diff `2d76371d..1133a931` bằng đúng diff của nhánh.
- Cổng: phạm vi **đầy đủ**. Reviewer không chạy cổng; dưới đây là log của I.
  - `I/verify-3.log` (sha `2d76371d`, porcelain 0): 7/7, 426 tệp / 8819 test, EXIT 0.
  - `I/e2e-4.log` (`2d76371d`): 329 qua / 0 hỏng / 5 bỏ qua, EXIT 0.
  - `I/verify-4.log` (sha `1133a931`, porcelain 0): "Tất cả các bước đều đạt", 426 tệp / 8827 test, **EXIT 0**.
  - `I/e2e-5.log` (`1133a931`): **329 qua / 0 hỏng / 5 bỏ qua, EXIT 0**.
  - `R3/U`:
    - đỏ: `red.log` (sha `2d76371d` + test mới), 11 hỏng / 42, exit 1;
    - xanh: `vitest.log` (sha `6ee43ecf`), 169/169. Lệnh này exit 1 chỉ vì ngưỡng gộp `src/lib/**` khi chạy một phần thư mục; bước độ phủ của `verify-4` đạt;
    - e2e `upload.spec.ts --repeat-each=10`: 60/60, exit 0;
    - typecheck, lint, length: exit 0.
- Độ phủ: đạt ngưỡng trong `verify-4`. Hai tệp đổi chính: `useFloorUploadScreen.ts` 93,45 % dòng / 86,33 % nhánh; `floorUploadGateway.ts` 96,26 % / 78,12 % (tầng screens không có ngưỡng riêng).
- Chuỗi thật F-14:
  - `I/chuoi-2.log` (sha `3b7c4b97`, BE `f545dcc`): `chuoi exit 0`. Như vậy điều kiện (b) của lượt 2 **đã đạt** trên cây sau R1.
  - Diff sau mốc chuỗi (`3b7c4b97..1133a931`) chỉ chạm phần upload/hàng đợi ngoại tuyến (chuỗi không đi qua), các bản sửa Nit, và một refactor `applyFloorLayerRead` giữ nguyên hành vi (xem 1c).
  - Tôi không đòi chạy thêm chuỗi. Nếu điều phối đọc câu 5 trong `duyet-nguoi-dung-2026-10-07.md` ("cây cuối") theo nghĩa chặt thì có thể chạy một lượt nữa trên `1133a931`.

## Kiểm theo khối [9]/[12]
- `git diff 3b7c4b97..6ee43ecf` không thêm dòng khớp `TODO|FIXME|ponytail:|.skip(|.fixme(|waitForTimeout|@ts-*|eslint-disable` trần (grep exit 1).
- Không đổi schema, router hay tệp cấu hình.
- 9 commit đều có dòng đầu ≤ 72 ký tự (dài nhất 71), đủ `Prompt:`, `Fix:` và `Debt-Prompt: DEBT-03`, mỗi commit chỉ chạm tệp của một chủ:
  - `018459ed`: `Button`, tệp không có chủ → `Prompt: DEBT-03`, như `InlineAlert`;
  - `1b8ecf1e`: `src/store/commit.ts` + `src/hooks/useAutosave.ts`, F-04x-1;
  - `2d76371d`: VersionHistory, F-08;
  - `5cf238c4`: FloorUploadScreen, F-03;
  - `6ee43ecf`: `vi.json`, F-05a.

## 1. Nit lượt 2 (FIX-454…458) — xác nhận
| Nit | Trạng thái | Bằng chứng |
|---|---|---|
| R2-1 nút `aria-disabled` trông như đang bật | **Đóng, sửa ở gốc chung.** | `018459ed` thêm `aria-disabled:opacity-40 aria-disabled:cursor-not-allowed` vào `buttonBaseStyles`, có bài trong `Button.test.tsx`. `2f4ed758` thêm assert cho class của nút "Tiếp tục xử lý". **Ảnh hưởng tới các màn khác** (điều phối hỏi): `git grep aria-disabled` trên `*.tsx` cho thấy ngoài `InputQualityGateFooter` không có `<Button>` nào truyền `aria-disabled`. Các chỗ dùng `aria-disabled` khác (WelcomeScreen, FurnitureLibraryPanelCard, ContextMenu, WallGeometryEditorOverlay, ScaleCalibrationPanel) là thẻ `<button>`/`<section>` thô, không qua `buttonBaseStyles`. `getButtonStyles` dùng ngoài `Button` chỉ ở hai thẻ `<a>` (MobileViewer, Viewer3D), không có `aria-disabled`. Ảnh chuẩn e2e không đổi (e2e-4, e2e-5 đều 0 hỏng). → Không màn nào khác đổi. |
| R2-3 `isRetryingSession` chỉ được ghi | **Đóng.** | `3c798089` bỏ trường này khỏi model, story và test. |
| R2-4 hai bản nạp lại N16 | **Đóng.** | `1b8ecf1e` thêm `applyFloorLayerRead` ở `src/store/commit.ts:316`; autosave (`useAutosave.ts:557`) và VersionHistory (`2d76371d`, `useVersionHistory.ts:345`) cùng gọi. Hành vi giữ nguyên: autosave trước so `scaleStatus` theo truthy, nay so `=== undefined`, tương đương vì kiểu là `'unresolved' \| undefined`. |
| R2-5 Enter bị chốt nuốt sau khi đổi tên bị từ chối | **Đóng.** | `744292bb`: chốt `committed` chỉ chặn blur; Enter (yêu cầu tường minh) luôn tới `onCommit`. Có bài mới. Trong màn thật, Enter hai lần khi lệnh đang bay không gây ghi đôi, vì lệnh đổi tên áp lên kho ngay nên lần sau gặp `draft === name`. |
| R2-6 PDF offline chưa chọn trang | **Đóng.** | `94d5d46c` thêm bài: chưa chọn trang thì mạng về cũng không tải. |

## 2. Phương án B cho P3-4 (NO-392) — `5cf238c4`, `6ee43ecf`
Thiết kế: mỗi tệp chờ mạng ghi **một** lệnh `uploadDrawing` làm dấu đếm "chờ đồng bộ" cho ConnectionStates; lệnh không mang `File`. Lệnh được gỡ ở mọi lối ra:
- `cancelTask`, nên phủ huỷ, xoá, gán lại, đổi trang, bị đẩy về khay;
- lúc lượt tải trực tuyến **bắt đầu**;
- khi rời màn (cleanup);
- khi mở màn, gỡ lệnh mồ côi của dự án (`clearOrphanUploads`).

Đánh giá từng điểm:
- **Một tệp một lệnh, không ghi trùng.** `dropQueued(id)` rồi `queuedRef.set(id, …)`, đồng bộ trên `Map`. Lệnh giữ dạng lời hứa nên gỡ được cả khi lượt ghi chưa xong (`useFloorUploadScreen.ts` nhánh offline và `dropQueued`).
- **Gỡ khi lượt tải trực tuyến bắt đầu (tác giả chọn):** đúng ngữ nghĩa.
  - Bộ đếm là "tệp đang chờ mạng". Khi lượt tải đã bắt đầu, tệp rời trạng thái ấy. Nếu lượt tải hỏng, thẻ ở `error` với nút thử lại, không quay về chờ, nên không còn gì để "đồng bộ".
  - Thử lại lúc ngoại tuyến đi lại nhánh offline và ghi lại đúng một lệnh.
  - Đổi lại, khi đang tải mà mất mạng thì bộ đếm không tăng. Chấp nhận được, vì màn tự báo lỗi kèm nút thử lại (quyet-dinh P-6).
- **Gỡ lệnh mồ côi lúc mở màn:**
  - Lệnh ghi mới đợi `orphansClearedRef`, nên không bị lượt dọn gỡ nhầm.
  - Chỉ gỡ lệnh có `kind === 'uploadDrawing'`; lệnh loại khác giữ nguyên.
  - Đúng với câu đã hứa trên màn: "tải lại trang thì cần chọn lại tệp".
- **Rời màn:**
  - Cleanup gỡ mọi lệnh của màn; `unmountedRef` chặn một lượt `validateFile` về muộn ghi lệnh mới.
  - Hai lần mount/unmount của StrictMode không làm hỏng: mount lại đặt cờ về `false`.
  - Effect phụ thuộc `[gateway]`; `gateway` ổn định vì là `useMemo` ở container (`FloorUploadScreen.container.tsx:85`) hoặc prop của test. Nên cleanup không chạy giữa chừng.
- **Lỗi hàng đợi:** `.catch(() => null)`. Hàng đợi đầy hay IndexedDB hỏng thì tệp vẫn chờ mạng trong màn, chỉ thiếu dấu đếm (P-4).
- **Nhãn hàng ConnectionStates:** `label` "Tải bản vẽ <tệp> khi có mạng", có khoá `floorUpload.pendingUploadLabel` (`6ee43ecf`, theo R-67).
- **Test:** đỏ trên `2d76371d` (11/42 hỏng, exit 1) → xanh 61/61, lặp 3 lượt. Có bài riêng cho "(b) rời màn khi tệp đang chờ mạng → lệnh gỡ" và cho `label`. `beforeEach` dọn hàng đợi của hai dự án dùng trong test (P-10).
- **Quyết định đã ghi đủ** (`R3/U/quyet-dinh.md` P-1…P-11), có phản biện. Các khẳng định tôi tự đọc lại mã: P-1, P-2, P-3, P-4, P-5, P-6 đúng.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| R3-1 | P3 | CON | **NO-400** (điều phối đã biết): hai tab cùng một dự án → tab mở sau gỡ lệnh "chờ đồng bộ" của tab trước, vì `clearOrphanUploads` gỡ theo dự án. Không mất dữ liệu: tab trước vẫn giữ `File` và tự tải. Chỉ bộ đếm thiếu, mà `ConnectionStatesContainer` hiện chỉ được gắn trong StateGallery. Nợ do chính phương án B sinh ra. | `src/screens/upload/FloorUploadScreen/floorUploadGateway.ts` (`clearOrphanUploads`) | Người dùng quyết: sửa (sessionId + Web Locks), hoặc duyệt chuyển DEBT-04. Đang chờ — điều kiện (a). |
| R3-2 | Nit | MNT | **`replayer` chưa phân biệt lệnh `uploadDrawing`.** Lệnh này chỉ là dấu đếm, nhưng `replayer` chưa có nhánh bỏ qua nó. Hiện vô hại vì `createReplayer` không có nơi gọi; bất biến đã ghi ở chú thích đầu `floorUploadGateway.ts` (P-9). | `src/lib/offline/replayer.ts:228` (`sendCommand`) | Khi nối replayer: `sendCommand` bỏ qua `uploadDrawing`. Chưa có dòng `DEBT.md` riêng (NO-401 là việc ConnectionStates đọc lại hàng đợi) — điều phối ghi cùng điều kiện (b), hoặc gộp vào NO-401. |

Không có P0, P1 hay P2 mới.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 4 | 0,60 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 5 | 0,15 |

Tổng: 4,85 / 5

## PHÁN QUYẾT: APPROVE WITH COMMENTS
Năm Nit của lượt 2 đều đã đóng. Bản sửa `Button` không làm đổi màn nào khác. Phương án B đúng thiết kế: một lệnh mỗi tệp, gỡ ở mọi lối ra, dọn lệnh mồ côi, gỡ khi rời màn. Gỡ lệnh lúc lượt tải bắt đầu là lựa chọn đứng được. Có test đỏ→xanh. Cổng đầy đủ trên `1133a931`: verify 7/7 và e2e 0 hỏng. Chuỗi thật F-14 xanh trên `3b7c4b97`.

Điểm 4,85 theo ma trận là APPROVE. Tôi ghi **WITH COMMENTS** vì khối [9] không cho đóng prompt khi còn một nợ do chính DEBT-03 sinh ra mà chưa được xử lý. Gộp `master` được khi:
- **(a)** Người dùng quyết NO-400 (R3-1): sửa (cần review đích cho diff đó), hoặc duyệt chuyển DEBT-04.
- **(b)** Sổ sách còn lại từ điều kiện (c) của lượt 2 đã xong:
  - `docs/fixes.md` có khối cho mọi FIX của DEBT-03 (tới FIX-460), kèm ghi chú K27 / `23d98fb7`, dòng đầu 74 ký tự, FIX-408;
  - `backend/prompts/F-11.md:55`;
  - dòng `DEBT.md` cho R2-2, NO-400, NO-401 và R3-2;
  - cập nhật F-03.md:110 nếu cần — phương án B đã khôi phục `EnqueueOfflineUploadInput`, nên câu ấy lại đúng.
