# Review merge fix/debt-03-fe-master → master (AppFront) — DEBT-03, lượt 2

- Ngày: 2026-10-07 · Reviewer: phiên /merge-review riêng (R-37), không phải tác giả.
- Lượt 1: `docs/reviews/2026-10-07-fix-debt-03-fe-master.md` (`c2731a75`, APPROVE WITH COMMENTS).
- Commit đầu nhánh: `3b7c4b97c324`, cây sạch (porcelain 0).
- Vòng sửa soát: `c2731a75..3b7c4b97`, gồm bốn merge R1 và 14 commit, 28 tệp, +677/−192.
  - U `fix/debt-03-w3-x1` @ `10cd7f16`: FIX-437…442.
  - M `fix/debt-03-w3-x2` @ `3a9ba155`: FIX-443…446.
  - V `fix/debt-03-w1-v` @ `ba7ef22e`: FIX-447…450.
  - S `fix/debt-03-w2-s` @ `85bf849c`: FIX-451…453.
  - Diff ròng của cây gộp đúng bằng tổng bốn nhánh (28 tệp = 9 + 5 + 6 + 8; +677 = 250 + 76 + 145 + 206), nên việc gộp không thêm gì.
- Cổng: phạm vi **đầy đủ**. Vòng sửa đổi mã nhiều vùng, có test mới và đổi giao diện gateway (R-33b). Reviewer không chạy cổng; dưới đây là log của I, dòng đầu mỗi log có `sha=3b7c4b97 porcelain=0`.
  - `I/verify-2.log`: `pnpm verify` 7/7 "Tất cả các bước đều đạt", 426/426 tệp test, **EXIT 0**.
  - `I/e2e-3.log`: **329 qua / 0 hỏng / 5 bỏ qua, EXIT 0**. Giống lượt 1, và 5 bài bỏ qua vẫn là các `test.fixme` có từ trước.
  - `I/no371-1.log`, `I/no371-2.log`: `--repeat-each=20 e2e/v2v3/notification-center.spec.ts`, **120/120 mỗi lượt, EXIT 0**.
- Log từng vùng (`R1/{U,M,V,S}`):
  - typecheck, lint, length: EXIT 0 ở cả bốn vùng.
  - vitest: U 352/352, M 148/148, V 65/65, S 333/333 (có độ phủ), EXIT 0.
  - Mỗi finding đổi hành vi đều có log đỏ EXIT 1 rồi xanh EXIT 0, hoặc log đột biến EXIT 1.
- Độ phủ: tổng đạt ngưỡng trong `verify-2` (bước "test + độ phủ" đạt). Tệp đổi lớn nhất (U): `useFloorUploadScreen.ts` 92,75 % dòng, 84,96 % nhánh; tầng screens không có ngưỡng riêng.
- Chuỗi thật F-14: `I/chuoi-1.log` (sha `c2731a75`, BE `aec5c2e`) **`chuoi exit 0`**, e2e fullstack 1 passed. Chuỗi này chạy **trước** R1, mà R1 chạm Xử lý, lời mời/phiên và phiên bản tầng. Xem điều kiện (b).

## Kiểm theo khối [9]/[12] trên vòng sửa
- `git diff c2731a75..3b7c4b97` không thêm dòng khớp `TODO|FIXME|ponytail:|.skip(|.fixme(|waitForTimeout|@ts-*|eslint-disable` trần (grep EXIT 1).
- Không đổi `src/lib/schemas/**`, router, cấu hình playwright/vitest. Tệp duy nhất dưới `src/routes/**` bị chạm là `sessionSetup.test.ts`, thuộc ngoại lệ [12] đã duyệt.
- 14 commit đều đúng mẫu:
  - dòng đầu ≤ 72 ký tự (dài nhất 69);
  - đủ `Prompt:`, `Fix:`, `Debt-Prompt: DEBT-03`;
  - mỗi commit chỉ chạm tệp của một chủ: `vi.json` là F-05a; FloorUploadScreen là F-03; InputQualityGate là F-05a; MeasurementTool là F-02; RoomLabel là F-04x-1; VersionHistory là F-08; InvitationAccept là F-09a; `sessionSetup.test` là F-01b; ProcessingScreen là F-05b.
- Assert:
  - `toBeDisabled` → `toHaveAttribute('aria-disabled','true')` là đổi theo đúng hành vi mới (P3-10c), không phải nới: bài vẫn khẳng định bấm không điều hướng, và nay việc đó phụ thuộc thật vào chốt `onClick`.
  - Các bài `enqueueOffline` được thay bằng bài khẳng định "không lệnh nào vào hàng đợi", mạnh hơn bài cũ (đột biến trong `R1/U/tai-hien-U.md`).

## Soát finding lượt 1
| # lượt 1 | Trạng thái | Bằng chứng |
|---|---|---|
| 1 P2 vi.json (6 chuỗi) | **Đóng.** | `51abd1b1` (FIX-437) thêm đủ 6 khoá, chữ khớp từng ký tự: `inputQualityGate.footer.continueWaitingReading/ReadFailed/NoDrawing`, `floorLayerSave.unnamedRoom`, `roomLabel…emptyError`, `measurementTool…sceneFailed`. `10cd7f16` (FIX-442) thêm khoá cho câu báo mới `displacedToTray`. |
| 2 P3 hoàn tác vào tầng đã có tệp | **Đóng.** | `65fee34e` (FIX-439): vé hoàn tác đọc `attachmentsRef`; tầng đã có tệp khác thì tệp về khay (`toTray()`) và có câu báo. Bài "hoàn tác xoá không đưa tệp về tầng đã nhận tệp khác…" khẳng định chỉ tệp ở tầng được tải. `red-u.log` exit 1 → `vitest.log` exit 0. |
| 3 P3 "dựng hỏng" báo đã dựng xong | **Đóng.** | `c377b9e5` (FIX-443): `liveStatusOf` báo `SCENE_FAILED_MESSAGE` khi `failed`. `M/red-P3-3.log` EXIT 1 → `green-P3-3.log` 44/44 EXIT 0. |
| 4 P3 NO-392 sót lệnh | **Đóng về kỹ thuật; còn chờ quyết sản phẩm** (xem nhận xét ở finding R2-1). | `65fee34e` (FIX-438) bỏ hẳn việc ghi `uploadDrawing` vào hàng đợi ngoại tuyến. Hết cả hai đường sót. |
| 5a NO-365 chốt `undoing` của hook | **Đóng.** | `R1/V/dot-bien-365.log`: bỏ chốt của hook → EXIT 1. |
| 5b N18 `peak ≤ 2` | **Đóng.** | `ba7ef22e` (FIX-449) giữ phản hồi bằng deferred. `dot-bien-368.log`: vượt trần → EXIT 1. |
| 5c NO-392 test | **Đóng.** | Bài mới ghim tính chất "không lệnh nào" qua chọn, thử lại, gán lại, xoá và tải hỏng; đột biến về mã `c2731a75` → đỏ `expected 8 to be 7`. |
| 5d `sessionSetup.test.ts:66` | **Đóng.** | `77d93031` (FIX-452) đếm `configureAuth` và `bootstrapSession`. `S/p3-5d-dot-bien-M1.log` và `M2.log` EXIT 1 → `p3-5d-xanh.log` EXIT 0. |
| 5e Enter rồi blur | **Đóng; lộ một lỗi thật đã sửa.** | `b68d9ae1` (FIX-445) thêm state `committed`. `M/red-P3-5e.log` EXIT 1 (gọi 2 lần) → `green-P3-5e.log` 57/57 EXIT 0. Ghi chú: trong màn thật lệnh đổi tên áp lên kho ngay, nên `name` thường đã theo kịp trước khi blur; lỗi chỉ lộ khi cha chưa cập nhật `name`. Sửa vô hại; xem Nit R2-5. |
| 6 P3 NO-371 | **Chấp nhận đóng ✅** cho kiểu hỏng lúc khởi động lạnh; còn một kiểu hỏng khác (xem finding R2-2). | S đo không có `beforeAll` trên Vite lạnh: 0/120 và 1/120 (`:65`, lượt 67/120, giữa chừng) → giữ `beforeAll` (`R1/S/tai-hien-P3-6.md`). Trên cây cuối có `beforeAll`: 0/120 ×2 (`I/no371-1.log`, `I/no371-2.log`); e2e cả bộ hai lượt (e2e-2, e2e-3) 0 hỏng. Kiểu hỏng của base là bài đầu mỗi worker, 6/120 (`w2/M/e2e-base-2.log`); kiểu này không còn xuất hiện ở hơn 480 lượt sau sửa. |
| 7 P3 toast quá hạn phiếu | **Đóng.** | `f2ec2fb8` (FIX-447): phiếu `expired` thì hiện dải `UNDO_EXPIRED_NOTICE`, không im lặng. `R1/V/red-r1.log` EXIT 1 → `vitest.log` EXIT 0. |
| 8 P3 `pending` đến muộn | **Đóng.** | `e7edf5dd` (FIX-451): xem nhận xét (2) bên dưới. `S/red-p3-8.log` EXIT 1 → `green-p3-8.log` 177/177 EXIT 0, NO-154 và NO-364 vẫn xanh. |
| 9 P3 N16 thiếu `level`/`scaleStatus` | **Đóng**, Nit R2-4. | `f2ec2fb8` (FIX-448): gateway đọc thêm `level` và `scaleStatus`; hook truyền đủ vào `replaceFloorLayer` và xoá `scaleStatus` cũ như autosave. |
| 10a Thử lại ở lời mời | **Đóng**, Nit R2-3. | `85bf849c` (FIX-453): một lượt một lúc; vùng `role="status"` báo "Đang kiểm tra kết nối." rồi câu lỗi; tiêu điểm chỉ về ô đầu khi dải biến mất mà tiêu điểm rơi về `body`. `S/red-p3-10.log` EXIT 1 → green 32/32. |
| 10b `outline-none` | **Đóng.** | `412bb92d` (FIX-441): `focus:ring-2`; có thêm `expectAccessible`. |
| 10c `disabled` không Tab tới được | **Đóng; sinh finding mới R2-1.** | `412bb92d`: `aria-disabled` + bỏ `onClick`; bài khẳng định `button.focus()` có tiêu điểm. |
| 11 P3 tệp về khay không báo | **Đóng.** | `65fee34e` (FIX-440): `announce(displacedSentence)` ở cả gán lại lẫn hoàn tác; có khoá `vi.json`. |
| 12 P3 nhãn log | **Đóng.** | `w3/X1/vitest-389-green-r1.log` EXIT 0 (sha 412bb92d), đã sửa nhãn trong `fix-428.md` và `tai-hien`. `w1/V/red-365-369-r1.log` có `sha=8b11b1bf`, EXIT 1 trên đúng bản test đã commit. |
| 13, 14 P3 K27 lịch sử | **Chấp nhận** ghi hồ sơ ở `docs/fixes.md`, không sửa lịch sử. Lý do: nhánh đã gộp `--no-ff` với trailer của mọi chủ (R-36); viết lại sẽ đổi sha mà mọi log, `nhanh-xong.txt` và phán quyết lượt 1 dẫn tới, nên hại hơn lợi. | **Điều kiện (c):** lúc review, `docs/fixes.md` chưa có khối nào của DEBT-03 (`grep FIX-388` rỗng). |
| 15 Nit chú thích | **Đóng 3/4.** | `InvitationAccept.tsx` (85bf849c), `roomLabelFixture.ts` (3a9ba155), `FloorUploadScreen.test.tsx` (65fee34e). Còn `backend/prompts/F-11.md:55` (AppBack, của điều phối) vẫn trỏ `useBillingScreen.ts:276` → điều kiện (c). |
| 16 Nit | **Đóng hoặc chấp nhận.** | Đã sửa: v15 có snapshot riêng (7ac76907, có test); câu chờ mạng chỉ đọc một lần (65fee34e); chốt ghim khi gateway ném đồng bộ (a736ecd0, `red-nit-pin.log` EXIT 1). Chấp nhận ghi hồ sơ, không sửa lịch sử: dòng đầu `6faf1e61` dài 74 ký tự; FIX-408 dùng cho hai việc. |

### Nhận xét theo câu hỏi của điều phối
1. **U bỏ việc ghi `uploadDrawing` vào hàng đợi ngoại tuyến (P3-4).** Về kỹ thuật là đúng.
   - Lệnh trong hàng đợi không mang được `File`, `createReplayer` không có nơi gọi, và lệnh sống qua cả lượt tải lại trang. Nên nó chỉ là một dòng "chờ đồng bộ" không bao giờ hết. Màn giữ `File` trong bộ nhớ (NO-389) nên vẫn tự tải khi mạng về, và có câu báo ngay trên màn.
   - Hệ quả phải nói rõ với người dùng: sau `65fee34e`, **không còn mã chạy thật nào ghi vào hàng đợi ngoại tuyến** (`addPendingCommand` chỉ còn trong `src/lib/offline` và test của nó). Vì vậy:
     - phần "chờ đồng bộ" của ConnectionStates (`ConnectionStates.container.tsx:106`) luôn rỗng;
     - `queueStore`/`replayer` thành hạ tầng không có nguồn ghi;
     - F-03.md:110 lỗi thời.
   - Đây là đổi hành vi người dùng thấy (mất chỉ báo chung giữa các màn), nên đúng là việc người dùng quyết. `R1/U/bao-cao.md` cũng ghi là không chạy tranh luận hai vai (memory `fe-change-needs-two-role-debate`).
   - Nếu người dùng duyệt: ghi nợ (DEBT-04) cho hạ tầng hàng đợi/replayer và phần "chờ đồng bộ" không còn nguồn ghi (gỡ, hoặc nối nguồn), và cập nhật F-03.md:110.
   - Nếu người dùng không duyệt: hướng thay là giữ lệnh nhưng gỡ ở mọi lối ra của tệp, cộng một lượt dọn lệnh `uploadDrawing` mồ côi lúc mở màn.
2. **S P3-8, mốc quan sát trong `createProgressReader`.** Không phá NO-154 hay NO-364, không có đua mới.
   - `observed` tăng ở `markSeen` (SSE) và ở mỗi lượt đọc có nội dung mới. Lượt đọc nhớ mốc lúc đi.
   - Một `pending` chỉ bị bỏ khi đã có nhịp mới hơn **và** nhịp ấy không phải `pending`. Lượt mới thật vẫn vào: hoặc không có gì mới trong lúc chờ (bài "still takes a pending…"), hoặc lượt đọc sau mang `pending` lần nữa vì mốc không đổi.
   - Bỏ một nhịp trả `null`, giống nhánh trùng nội dung sẵn có, nên nơi gọi không phải đổi gì.
   - NO-154 (gia hạn qua cổng tiến độ) không đi qua nhánh này. Bài `useProcessingScreen` NO-154 và NO-364 có trong 177/177.
3. **M P3-5e** là lỗi thật của ô tên (thêm ở b1e64d17, DEBT-03) khi `name` của cha chưa theo kịp; đã sửa và có test đỏ→xanh. Xem Nit R2-5.
4. **NO-371:** xem dòng 6 trong bảng trên và finding R2-2.
5. **Mọi finding lượt 1 đã đóng thật**, trừ những dòng ghi "chấp nhận ghi hồ sơ" (13, 14, Nit 74 ký tự, FIX-408) và `F-11.md:55` — phụ thuộc điều kiện (c).

## Finding mới
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| R2-1 | P3 | LOG/UX (LUAT bảy trạng thái) | **Nút "Tiếp tục xử lý" bị chặn bằng `aria-disabled` nhưng trông như đang bật.** `Button` chỉ tô dạng vô hiệu (`opacity-40 cursor-not-allowed`, `buttonVariants.ts:47`) khi có prop `disabled`; `aria-disabled` không được tô gì. Ở ba trạng thái chặn (đang đọc, đọc hỏng, chưa có bản vẽ), người nhìn thấy một nút chính sáng rõ, bấm thì không có gì xảy ra; câu lý do vẫn nằm cạnh nút. Do vòng sửa R1 sinh ra (FIX-441). Tái hiện: dựng màn NO-361 rồi đọc class của nút, không có `opacity-40`. | `src/screens/upload/InputQualityGate/InputQualityGateFooter.tsx:70-71`; `src/components/ui/buttonVariants.ts:47` | Thêm `className="aria-disabled:opacity-40 aria-disabled:cursor-not-allowed"` tại nút; hoặc cho `Button` tô theo `aria-disabled` (gốc chung, có lợi cho mọi nơi). Thêm một assert về class. Chủ F-05a (hoặc chủ `Button`). |
| R2-2 | P3 | TEST (chập chờn) | **NO-371 còn một kiểu hỏng khác chưa rõ gốc:** khi không có `beforeAll`, trên Vite lạnh, có 1/240 lượt hỏng giữa chừng (`:65`, lượt 67/120, heading "Thông báo" quá 15 s, máy chạy 6 worker). `beforeAll` không nhắm vào kiểu này. Trên cây cuối có `beforeAll` thì 0/240, nhưng tần suất thấp nên chưa đủ để nói là đã hết. Đây là chập chờn có từ trước (không do DEBT-03 gây ra), nên theo luật phạm vi người dùng duyệt thì chuyển DEBT-04. | `e2e/v2v3/notification-center.spec.ts:65`; `R1/S/e2e-p3-6-luot2.log` | Ghi một dòng `DEBT.md` ⬜ cho DEBT-04, kèm số đo 1/240. |
| R2-3 | Nit | MNT (R-10) | **`isRetryingSession` chỉ được ghi, không ai đọc.** View chỉ dùng `retryNotice`; nút "Thử lại" không có trạng thái chờ, lượt bấm thêm chỉ bị chốt bỏ qua. | `src/screens/auth/InvitationAccept/useInvitationAccept.ts:89,341` | Bỏ trường này, hoặc dùng nó (`loading` hay `aria-busy` cho nút). |
| R2-4 | Nit | MNT (R-07) | **VersionHistory chép lại thân `reloadFloor` của autosave**, gồm `level`, `scaleStatus` và việc xoá `scaleStatus` qua `updateFloorMeta`. Hai bản phải được giữ đồng bộ bằng tay. | `src/screens/export/VersionHistory/useVersionHistory.ts:343-357` vs `src/hooks/useAutosave.ts:552-566` | Ở lượt chạm sau, cho một bản gọi bản kia. |
| R2-5 | Nit | LOG | **Chốt `committed` có thể nuốt im lặng một lượt Enter.** Khi lệnh đổi tên bị từ chối (`built.ok === false`, `name` không đổi), `committed` vẫn giữ tên ấy, nên Enter lại cùng chữ không làm gì — kể cả không hiện lại câu từ chối. | `src/screens/qc/RoomLabelReview/RoomLabelNameField.tsx:78` | Xoá `committed` khi `onCommit` báo từ chối, hoặc chấp nhận. |
| R2-6 | Nit | TEST | **Bài offline của PDF nhiều trang bỏ mất một vế.** Bài "chọn trang lúc ngoại tuyến…" bỏ câu khẳng định cũ "chưa chọn trang thì ngoại tuyến cũng chờ". Bài mới chỉ ghim nhánh đã chọn trang. | `useFloorUploadScreen.test.ts:1258-1279` | Thêm `expect(createUpload).not.toHaveBeenCalled()` sau `setOnline(true)` khi chưa chọn trang. |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 5 | 0,15 |

Tổng: 4,78 / 5 (chỉ có P3 và Nit)

## PHÁN QUYẾT: APPROVE WITH COMMENTS
Mọi finding lượt 1 đã đóng có bằng chứng, hoặc được chấp nhận ghi hồ sơ với lý do đứng được (13, 14 và hai Nit lịch sử). Không có P0, P1 hay P2. Cổng đầy đủ trên `3b7c4b97`: verify 7/7, e2e 0 hỏng, NO-371 ×20 hai lượt 0 hỏng.

Điểm 4,78 theo ma trận là APPROVE. Tôi ghi **WITH COMMENTS** vì còn ba việc phải xong trước khi gộp `master`:
- **(a) Người dùng quyết P3-4** (thôi ghi hàng đợi ngoại tuyến; hệ quả là ConnectionStates "chờ đồng bộ" mất nguồn ghi). Duyệt → ghi nợ DEBT-04 như nhận xét (1). Không duyệt → làm lại theo hướng thay, và cần lượt review 3 cho diff đó.
- **(b) Một chuỗi thật F-14 trên cây cuối** (sau R1, tức `3b7c4b97` hoặc mới hơn), theo câu 5 trong `duyet-nguoi-dung-2026-10-07.md`. Chuỗi xanh hiện có (`I/chuoi-1.log`) chạy trên `c2731a75`, trước R1, mà R1 chạm Xử lý, phiên và phiên bản tầng.
- **(c) Sổ sách của điều phối:**
  - `docs/fixes.md` có khối cho mọi FIX của DEBT-03 (FIX-385…453, theo [10]), trong đó ghi rõ dòng NO-370 nằm ở `23d98fb7`, các lệch K27 của finding 14, dòng đầu 74 ký tự của `6faf1e61` và FIX-408 dùng cho hai việc;
  - sửa `backend/prompts/F-11.md:55`;
  - `DEBT.md`: thêm dòng R2-2 (DEBT-04), và dòng P3-4 nếu người dùng duyệt.

R2-1 do chính vòng sửa sinh ra, nên theo khối [9] phải sửa: một commit nhỏ với test đỏ→xanh, kiểm đích typecheck + vitest `src/screens/upload/InputQualityGate`. Commit ấy không cần review lượt 3 nếu diff chỉ là class và assert. Hoặc người dùng duyệt chuyển nó sang DEBT-04. Các Nit R2-3…R2-6 không chặn.
