# Review merge fix/debt-03-fe-master → master (AppFront) — DEBT-03

- Ngày: 2026-10-07 · Reviewer: phiên /merge-review riêng (R-37), không phải tác giả · Commit đầu nhánh: `c2731a75bf68` (cây sạch, `git status --porcelain` rỗng)
- Lúc bắt đầu, đầu nhánh là `dac5e8eff122`. Trong lúc review nhánh thêm 13 commit, tôi soát cả 13:
  - 8 commit `docs(...)` chỉ đổi chú thích nhắc Billing, FIX-412 (`3b8bc774`…`868260e5`).
  - `786c2810`: xoá `MeasurementTool/vi.json.fragment`, FIX-434 / NO-396. Bằng chứng: `I/no396-bang-chung.log` (33 lá, thiếu 0). Không script/cấu hình nào đọc `*.fragment`.
  - `2213a203`: `.notes/contract-data.md`, NO-395 (người dùng duyệt). `c1996c76` revert rồi `c2731a75` áp lại y nguyên, chỉ để đổi FIX-435 → FIX-436. Diff ròng `464c6c95..c2731a75` rỗng. Câu ghi chú khớp mã thật (`networkMonitor.ts:85`, `pingOnline = true`).
  - `464c6c95`: merge w2-s @ `f1b3349d`, NO-372, ngoại lệ [12] người dùng duyệt (`duyet-nguoi-dung-2026-10-07.md` câu 2).
- Phạm vi review: `5bf3a9ee...c2731a75` (base so sánh `cbfdbaae`), trừ `merge/ghep-master` `81ad9154..5bf3a9ee` đã có review APPROVE (`2026-10-06-merge-ghep-master-round-2.md`). Nit lượt 2 của review đó đã đóng bằng `a049430b` (FIX-409): `vi.spyOn` trong khối NO-154, có `mockRestore`.
- Gồm các cụm: w1-a, w1-v, w1-q, w2-s (+NO-372), w2-p, w2-m, w3-x1, w3-x2, và các commit vá của I. 95 tệp, khoảng +2,6k / −3,7k dòng, phần lớn là xoá Billing.
- Chia việc: bốn subagent chỉ đọc theo vùng tệp, reviewer tự phân xử. Mọi finding P2 và mọi finding P3 dưới đây ghi "đã kiểm" là reviewer đã tự đọc lại mã.
- Cổng: phạm vi **đầy đủ** trên cây gộp. Không chạy lại, đọc log (dòng đầu mỗi log có `sha=` và `porcelain=`):
  - `I/verify-1.log`: sha `0b7a2520`, porcelain 0. `pnpm install --frozen-lockfile && pnpm verify` 7/7, **EXIT 0**: 426/426 tệp, 8804 test, ngưỡng độ phủ đạt, build và kích thước gói đạt.
  - `I/e2e-2.log`: sha `dac5e8ef`. **329 qua / 0 hỏng / 5 bỏ qua, EXIT 0**.
    - Mốc G (`GHEP-MASTER/e2e-1.log`): 327 qua / 2 hỏng / 16 bỏ qua.
    - Bỏ qua giảm 11 = 4 billing + 5 share-dialog + 1 tour-chip + 1 export, khớp cụm M. Tổng 345 → 334.
    - 5 bài bỏ qua còn lại đều là `test.fixme` có từ trước (processing, floor-manager, viewer-panels ×3).
  - NO-377: `I/no377-1.log` (0b7a2520) và `I/no377-2.log` (dac5e8ef), `--repeat-each=10` song song, 10/10 qua, EXIT 0 cả hai.
- Phần sau `0b7a2520` đi đường đích (R-33b):
  - `dac5e8ef`: chỉ đổi ảnh PNG; e2e-2 đầy đủ xanh.
  - 9 commit chú thích, xoá fragment, `.notes`: không đổi hành vi.
  - NO-372: `I/no372-dich.log` (sha `464c6c95`, porcelain 0) EXIT-vitest 0, 208/208.
  - Reviewer tái hiện tại chỗ, 1/3 lượt được phép: `pnpm exec vitest run src/routes/SessionBootstrap.test.tsx src/routes/sessionSetup.test.ts src/screens/auth/InvitationAccept src/components/feedback/InlineAlert.test.tsx` trên sha `c2731a75`, porcelain 0 → **5 tệp / 60 test, EXIT 0**. Đã kiểm trước đó không có tiến trình vitest/verify nào khác.
- Độ phủ: tổng đạt ngưỡng theo `verify-1.log` (sha `0b7a2520`). Commit mã duy nhất sau đó là NO-372 (+3/−1 dòng trong `SessionBootstrap.tsx`, có test). Phần này không đo lại (phạm vi đích).
- **Điều kiện còn treo, không do review này chạy:** chuỗi thật F-14 trên `c2731a75` (`I/chuoi-1.log`). Lúc ghi phán quyết chuỗi đang chạy, ở bước dựng image. [11] mục 4 đòi chuỗi này xanh vì nhánh chạm phiên, Xử lý và phiên bản tầng.

## Kiểm theo khối [9]/[11]/[12]
- Không đổi `src/lib/schemas/**`, `src/api/schemas/**`, `src/routes/router.tsx`, `vendor/`, `eslint-rules/`, ngưỡng `vitest.config.ts`, `playwright*.config.ts`, `.github/`, `package.json`, lockfile.
- `src/routes/**` chỉ đổi đúng hai chỗ ngoại lệ đã duyệt: `sessionSetup.ts` + test, và `SessionBootstrap.tsx` + test.
- InvitationAccept được sửa thay cho AuthScreen (đã quyết).
- [11] mục 3: `git diff cbfdbaae..c2731a75` không thêm dòng khớp `TODO|FIXME|ponytail:|\.skip\(|\.fixme\(|waitForTimeout|@ts-ignore|@ts-expect-error|eslint-disable` trần.
  - `setTimeout(resolve, SLOW_SERVER_MS)` ở `InputQualityGate.test.tsx:683,691` chạy dưới đồng hồ giả (`clock.advance`), không phải ngủ thật.
  - Không bài nào bị nới assert. Các `expect` bị xoá chỉ thuộc phần mã đã gỡ (`listVersions`, `undoRestore`, `diff` của gateway, Billing). Bài NO-360 được chuyển vào `it.each` và có thêm một assert. `'Chưa đặt tên 3'` → `'0'` đi theo bộ mẫu, chặt như cũ.
- Hợp đồng FE–BE:
  - N7 `limit=200` khớp `limit` (1–200, mặc định 50) ở `docs/contracts/openapi.json` và BE-BIND.
  - `buildUrl` (`src/lib/http/client.ts:89-100`) nối thêm `limit` vào đường đã có `?cursor=`.
  - `floorUploadGateway` chỉ đổi giao diện nội bộ FE.
- Các quyết của điều phối, đều đúng:
  - NO-374 sửa ở kho: `src/store/commit.ts` `FloorLayerReplacement.dimensions`; cả ba đường nạp N16 đều truyền vào.
  - NO-390 sửa ở `networkMonitor`. Đã soát mọi nơi đọc nó: ConnectionStates, MobileViewer, CollaborationLayer, `watchNetwork`, replayer (replayer chưa có nơi gọi).
  - NO-358 sửa bộ mẫu, giữ `min(1)`.
  - NO-377 đóng mà không cần FIX mới (FIX-346 đã có trong base).
  - Ảnh chuẩn dashboard (`dac5e8ef`): khác base 634 px trong một khung khoảng 96×11 px ở (347,613)–(442,623), tức một dòng chữ "0/132 tường đã duyệt" → "0/0". Ảnh mới trùng từng byte với `I/dashboard-1440-actual.png`. Không đổi ngưỡng.
- K27 và trailer:
  - Mọi commit không phải merge đều có `Prompt:`, `Fix: FIX-nnn`, `Debt-Prompt: DEBT-03`, dòng đầu theo Conventional Commits. Ngoại lệ ở finding 13–14.
  - Tệp không có chủ (`InlineAlert`, `expectSentenceCase`, `.notes`) mang `Prompt: DEBT-03`.
- Bảng [11] mục 2 (`I/bao-cao.md` mục 5): mọi NO đóng ✅ đều có test chặn tái phát, red trên base là EXIT 1 và green là EXIT 0 (log ở `w1/*`, `w2/*`, `w3/*`).
  - Ngoại lệ hợp lệ: NO-366, 375, 378, 396 là mã chết, chứng minh bằng `git grep` rỗng. NO-363 là bất biến đã đúng sẵn, chứng minh bằng đột biến đỏ (`no363-dot-bien.log`). NO-355, 356 là xoá bài bỏ qua; `router.test.tsx:178` khẳng định không còn route.
  - NO-372: `w2/S/red-399.log` (EXIT 1, 1 bài hỏng) → `green-399.log` (26/26, EXIT 0).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LUAT R-67 (TEST) | **6 chuỗi hiển thị mới không có khoá `vi.json`**, nên `expectVietnamese` không soát chúng. Đã kiểm bằng `grep -c` trên `vi.json` = 0. Q (3): `continueWaitingReading`, `continueReadFailed`, `continueNoDrawing`; các câu anh em trong cùng khối `COPY` đều có khoá, ví dụ `continueBlockedGeneric` ở vi.json:723. A (2): `LAYER_SAVE_MESSAGES.unnamedRoom` ("Có phòng chưa đặt tên…", fragment cụm A tự ghi "không thêm vào vi.json") và `NAME_EMPTY_ERROR` ("Tên phòng không được để trống."). X2 (1): `SCENE_FAILED_MESSAGE` ("Chưa dựng được mô hình để đo…"). Nợ do chính DEBT-03 sinh, nên không thuộc luật chuyển DEBT-04. | `src/screens/upload/InputQualityGate/useInputQualityGate.ts:149-151`; `src/lib/autosave/spatialLayerSave.ts:84`; `src/screens/qc/RoomLabelReview/RoomLabelNameField.tsx:37`; `src/screens/viewer/MeasurementTool/useMeasurementTool.ts:194` | Một commit `fix(i18n)` (chủ `vi.json`, F-05a, như FIX-407) thêm 6 khoá; hoặc ghi dòng `DEBT.md` (R-34). |
| 2 | P3 | CON / NO-393 | **Hoàn tác xoá đưa hai tệp về cùng một tầng.** `undo` trả lại `removed` kèm `floorId` và gọi `startUpload`, nhưng không chạy luật "một tầng, một tệp" mới (`:717-733`). Tái hiện: offline, tệp A khớp L3 → xoá A → gán B vào L3 → Hoàn tác trong 8 s → A và B cùng L3, cả hai tải khi mạng về. Đúng lỗi NO-393 trên một đường còn sót. Đã kiểm mã. | `src/screens/upload/FloorUploadScreen/useFloorUploadScreen.ts:785-795` | Trong `undo`, tầng đã có tệp khác thì trả A về khay (`floorId: null`); thêm một test. Chủ F-03. |
| 3 | P3 | LOG / NO-385 | **Trạng thái mới "dựng hỏng" vẫn báo "Mô hình đã dựng xong."** `liveMessage` chỉ bị ghi đè khi `viewerState === 'loading'`. Khi `mountedScene.failed`, màn ra `error` nhưng thanh trạng thái (live) vẫn đọc READY_MESSAGE của vỏ. Cùng lớp lỗi với NO-388/391, phát sinh từ `58d29763`. Đã kiểm mã. | `src/screens/viewer/MeasurementTool/useMeasurementTool.ts:1005-1013` | Ghi đè `liveMessage` cả nhánh `failed`; thêm assert vào bài "worker sập". Chủ F-02. |
| 4 | P3 | RES / NO-392 | **NO-392 mới sửa một phần.** `dropQueued` chỉ chạy khi `done`, retry, gán lại, xoá. Hai trường hợp còn sót lệnh: lượt tải lại kết thúc `error` rồi người dùng bỏ đi; hoặc tải lại trang khi tệp đang chờ mạng. Lệnh nằm mãi trong IndexedDB và ConnectionStates đếm "chờ đồng bộ" mãi. | `useFloorUploadScreen.ts:525` | Ghi nợ. Hướng gọn hơn (F-03 quyết): màn đã giữ `File` trong bộ nhớ (NO-389) thì thôi ghi `uploadDrawing` vào hàng đợi ngoại tuyến, xoá được `queuedRef`, `dropQueued`, `dropOffline`. |
| 5 | P3 | TEST | **Bài kiểm không ghim được nhánh nó tuyên bố chặn:** | | Thêm assert hoặc đổi tên bài. Bài N18: giữ phản hồi bằng deferred như bài NO-376. |
| | | | (a) bài bấm đúp NO-365 vẫn xanh nếu xoá chốt `undoing` của hook, vì chốt `reverting` của gateway gánh thay; | `VersionHistory.test.tsx:655-661` | |
| | | | (b) bài "≤ 2 lượt N18 đang bay" (`peak ≤ 2`) không thể đỏ, vì lượt giả chỉ sống một microtask; | `VersionHistory.test.tsx:868-916` | |
| | | | (c) NO-392 không bắt được việc xoá `dropQueued` ở `removeFile`/`reassign`; | `useFloorUploadScreen.test.ts:656` | |
| | | | (d) bài "thử lại khi đã cấu hình…" không khẳng định `configureAuth` không bị gọi lại, và xanh cả trên base; | `src/routes/sessionSetup.test.ts:66` | |
| | | | (e) bài Enter/blur không blur. | `RoomLabelNameField.test.tsx` (6faf1e61) | |
| 6 | P3 | TEST / NO-371 | **Bằng chứng xanh của NO-371 chưa chắc:** cả hai lượt 20× sau sửa chạy trên cache Vite đã ấm (tai-hien tự nhận); lượt đỏ chỉ đỏ ở 1/2 lượt base. Lượt e2e-2 cả bộ xanh là thêm một điểm dữ liệu. Bản sửa là chờ điều kiện (đúng luật), nhưng là bản thứ ba của cùng một màn làm ấm theo từng spec. | `e2e/v2v3/notification-center.spec.ts:50-56` | Gốc chung: `server.warmup` của Vite hoặc `globalSetup` của Playwright, ghi nợ. |
| 7 | P3 | LOG | **Hoàn tác N19 hỏng tạm:** toast "thử lại" sống theo thời hạn mặc định của toast, không theo hạn còn lại của phiếu (8 s tính từ lúc phục hồi). Bấm sau hạn thì không có phản hồi nào. | `src/screens/export/VersionHistory/useVersionHistory.ts:387-390` | Truyền thời gian còn lại của phiếu, hoặc báo `UNDO_EXPIRED_NOTICE`. |
| 8 | P3 | CON | **Một nhịp `pending` đến muộn kéo thanh tiến độ về 0.** Nó bỏ qua `keepObservedDone`. Cụm P đã nhận rủi ro này (P-10). | `processingGateway.ts:574` | Ghi nợ; so mã lượt chạy trước khi đặt lại. |
| 9 | P3 | LOG | **Nạp lại N16 của VersionHistory là bản riêng**, không mang `level`/`scaleStatus`, trong khi `useFloorLayerAutosave().reloadFloor` đã làm đủ. Test lại ghim đúng ba khoá. Chỉ hỏng nếu N19 đổi được tỉ lệ. | `useVersionHistory.ts:339-349`; `VersionHistory.test.tsx:399` | Đi qua `reloadFloor` của autosave. |
| 10 | P3 | a11y (LUAT bảy trạng thái) | **Ba lỗi a11y nhỏ:** | | Như từng dòng dưới. |
| | | | (a) InvitationAccept "Thử lại": chuyển tiêu điểm ngay, không có trạng thái chờ; thử lại hỏng thì không báo gì mới; | `InvitationAccept.tsx:42-45` | Thêm cờ pending; chỉ chuyển tiêu điểm khi thành công. |
| | | | (b) chỗ đỡ tiêu điểm khi ghi lỗi có `outline-none`, nên không thấy tiêu điểm (WCAG 2.4.7); | `InputQualityGate.tsx`, wrapper `writeErrorRef` | Bỏ `outline-none` hoặc dùng vòng `focus-visible`. |
| | | | (c) "Tiếp tục" dùng `disabled`, nên Tab không tới được lý do `aria-describedby` (lý do vẫn hiện bằng chữ). | `InputQualityGateFooter.tsx:68` | `aria-disabled` + chốt có sẵn. |
| 11 | P3 | UX | **Tệp bị thay ở một tầng về khay mà không báo.** Tệp đã `attached` trông lại như "chờ". | `useFloorUploadScreen.ts:722-733` | `announce` khi đẩy tệp về khay. |
| 12 | P3 | TEST (bằng chứng) | **Hai log bằng chứng không đúng nhãn:** | | Sửa nhãn trong `fix-428.md`; từ nay log ghi `sha=`. |
| | | | `w3/X1/vitest-389-green.log` kết thúc EXIT 1 nhưng báo cáo gọi là xanh. Các lượt sau thay thế nó: `vitest-cov-b` 82/82 và `vitest-c-green` 49/49, EXIT 0. | `w3/X1/vitest-389-green.log` | |
| | | | `w1/V/red-365-369.log` đỏ trên bản test cũ hơn (dòng 651/687 thay vì 659/695) và không có `sha=`. | `w1/V/red-365-369.log` | |
| 13 | P3 | K27 / truy vết | **Bản sửa NO-370 nằm trong commit của chủ khác.** `wallsTotalCount: 132 → 0` (Sunrise, dữ liệu F-07) nằm trong `23d98fb7` (`Prompt: F-08`, FIX-386, gỡ `listVersions`). `af01f518` (F-07, FIX-388) chỉ đổi chú thích và thêm test. Đỏ→xanh base→HEAD vẫn đúng (`w1/A/red1.log` đỏ, `green-370.log` xanh), nhưng đỏ→xanh theo từng commit của FIX-388 thì không. Đã kiểm `git show 23d98fb7`. | `src/api/__mocks__/client.ts:1137` @ `23d98fb7` | Không viết lại lịch sử đã merge `--no-ff`. Ghi vào `docs/fixes.md` FIX-388: "dòng dữ liệu nằm ở 23d98fb7". |
| 14 | P3 | K27 | **Commit chạm tệp ngoài `so_huu` của chủ ghi trên trailer**, đều là hệ quả trực tiếp của bản sửa, không đổi logic người khác: | | Điều phối chốt một luật chủ cho `e2e/**` và tệp không có chủ; xin người dùng xác nhận chủ của `InlineAlert` (`00-SO-TRA.md:575`). |
| | | | `c75e31fb` (F-05b) sửa `PipelineGraph.test.tsx` (F-01b); | `c75e31fb` | |
| | | | `657a19d6` (F-09a) sửa `stateGalleryManifest.ts` (F-01b); | `657a19d6` | |
| | | | `09e6e478` (F-03) sửa `CollaborationLayer`, không có chủ, chỉ chú thích; | `09e6e478` | |
| | | | `8cb184f5` (F-04x-1) sửa `e2e/v7`; | `8cb184f5` | |
| | | | `7fe9dc30` dùng `Prompt: DEBT-03` cho `InlineAlert`, tệp không có chủ, do điều phối tự quyết. | `7fe9dc30` | |
| 15 | Nit | MNT | **Chú thích cũ:** | | Sửa chú thích ở lượt chạm sau. |
| | | | nói nút của dải "không mang `type`", sai sau 7fe9dc30; | `InvitationAccept.tsx:81` | |
| | | | còn nói "ba tên rỗng"; | `roomLabelFixture.ts:44-45` | |
| | | | còn nói pingOnline "khởi tạo `false`"; | `FloorUploadScreen.test.tsx:614-615` | |
| | | | `F-11.md:55` (AppBack, ngoài nhánh) còn trỏ `useBillingScreen.ts:276`, tệp đã xoá. | `backend/prompts/F-11.md:55` | |
| 16 | Nit | MNT | **Linh tinh:** | | Không bắt buộc. |
| | | | dòng đầu commit `6faf1e61` dài 74 ký tự (> 72); | `6faf1e61` | |
| | | | FIX-408 dùng cho hai việc khác nhau (`7abe75bc` F-08, `dac5e8ef` F-07); | `7abe75bc`, `dac5e8ef` | |
| | | | v15 dùng chung snapshot với v14 mà vẫn có số đếm diff khác 0; | `versionHistoryFixtures.ts:226` | |
| | | | thông báo chờ mạng đọc một lần cho mỗi tệp; | `useFloorUploadScreen.ts:559` | |
| | | | chốt `pinInFlightRef` kẹt nếu gateway tiêm vào ném đồng bộ (gateway thật trả promise). | `useMeasurementTool.ts:780` | |

Không có P0/P1. Không tìm thấy:
- đường nào kẹt `aria-busy=true` (canvas luôn được gắn: `ViewerViewport.tsx` `renderScene`; `unavailable`/`failed`/`idle` đều kết thúc `building`);
- rò chỗ của giới hạn N18 (`held` nhả đúng một lần; lượt xếp hàng bị huỷ rời hàng);
- chốt ghim bị rò khi promise bị từ chối (`.finally`);
- tải đôi khi mạng về (effect chỉ chạy khi `isOnline` đổi, `startUpload` xoá cờ chờ).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 4 | 0,60 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 4 | 0,40 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 3 | 0,21 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |

Tổng: 4,43 / 5

## PHÁN QUYẾT: APPROVE WITH COMMENTS
Không có P0/P1. Cổng đầy đủ: verify 7/7 và e2e 0 hỏng, với số bỏ qua giảm đúng 11. Mọi NO đóng ✅ có test chặn tái phát đỏ trên base, xanh trên nhánh (hoặc `git grep` / đột biến, khi nợ là mã chết hoặc bất biến). Không nới assert, không skip/retries/chờ thời gian, không đổi schema hay hợp đồng. Các ngoại lệ đã duyệt đều nằm đúng phạm vi.

Điểm 4,43 theo ma trận là APPROVE. Tôi hạ một bậc xuống **WITH COMMENTS** vì finding 1 (P2), cùng finding 2 và 3 (P3), là nợ **do chính DEBT-03 sinh ra**. Theo khối [9] ("không kết thúc prompt với dòng mở") và luật phạm vi người dùng duyệt ngày 2026-10-07 (chỉ nợ *không do DEBT-03 gây* mới được chuyển DEBT-04), các nợ này không được chuyển im lặng sang DEBT-04.

Merge được, kèm điều kiện:
- (a) Chuỗi thật F-14 trên `c2731a75` (`I/chuoi-1.log`) xanh — [11] mục 4.
- (b) Trước khi đóng prompt, chọn một trong hai: sửa finding 1 (một commit `fix(i18n)`, đích typecheck + vitest các tệp liên quan) cùng finding 2 và 3 (mỗi cái một commit có test đỏ→xanh, chủ F-03 và F-02); **hoặc** người dùng duyệt chuyển ba mục này sang DEBT-04.
- (c) Ghi `DEBT.md` (R-34) cho mọi finding P3 còn lại không sửa (4–14), và sửa nhãn bằng chứng ở finding 12–13 trong `docs/fixes.md` và `fix-428.md`.

Việc đóng dòng `DEBT.md` của NO-355…NO-396 là của điều phối sau phán quyết này.
