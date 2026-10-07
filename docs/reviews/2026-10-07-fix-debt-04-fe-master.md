# Review merge fix/debt-04-fe-master → master (AppFront) — DEBT-04, lượt 1

- Ngày: 2026-10-07 · Reviewer: phiên /merge-review riêng (R-37), không phải tác giả · Commit đầu nhánh: `bb058bf28ba2`
- Worktree `C:/Users/mxuan/orca/workspaces/AppFront/debt04-i`, base `e0a9ec08` (= master). `git status --porcelain` rỗng.
- Phạm vi: `e0a9ec08..bb058bf2`, gồm hai merge (`070e1bc7` cụm D, `bb058bf2` cụm O) và 6 commit FIX. 15 tệp, +841/−40. Phần logic khoảng 260 dòng, phần còn lại là test, nên chưa tới mức tách MNT-05.
  - D: `63c3af4e` FIX-481 (NO-397, F-05a), `8658f1eb` FIX-482 (NO-398, F-08).
  - O: `657fcd89` FIX-461 (NO-400, F-03), `5ea265c7` FIX-462 (NO-402, F-03), `61d7f563` FIX-463 (NO-401, F-03), `d86634f8` FIX-464 (NO-401, ConnectionStates, `Prompt: DEBT-04` vì tệp không có chủ trong sổ, xem `O/fix-464.md`).
- Cổng: phạm vi **đầy đủ** (lượt 1, R-33b điều kiện 1). Reviewer không chạy lại cổng vì máy bị hạn chế; dưới đây là log của I, mỗi log có dòng đầu `sha=bb058bf2 porcelain=0`.
  - `pnpm verify`: mã thoát **0**, 7/7 bước đạt: typecheck, lint, import vòng, test + độ phủ, build, kích thước gói, độ dài file (`backend/dieu-phoi/chay/DEBT-04/I/verify-1.log`).
  - e2e cả bộ, ba lượt, cả ba EXIT 1. Không bài hỏng nào chạm vùng diff:
    - `e2e-1.log`: 328/1/5, hỏng `pascal-viewer.spec.ts:631` (B-3).
    - `e2e-2.log`: 327/2/5, hỏng `auth/login.spec.ts:52` và `v4v5/pipeline-graph.spec.ts:51`. Lượt này chạy lúc cụm B dựng 10+ container; cả hai bài đều xanh ở e2e-1 và e2e-3.
    - `e2e-3.log`: 328/1/5, lại hỏng B-3.
  - B-3 là lỗi có sẵn:
    - `pascal-base.log`, base `e0a9ec08`, `--repeat-each=5`: 3 hỏng, trong đó B-3 hỏng 2/5.
    - `pascal-i.log`, nhánh, `--repeat-each=5`: 45/45, EXIT 0.
    - Diff không chạm `pascal`, `auth`, `pipeline`.
  - Reviewer chạy tại chỗ: `npx vitest run --coverage` trên `src/lib/offline`, `FloorUploadScreen/useFloorUploadScreen.test.ts`, `src/screens/system/ConnectionStates`, `VersionHistory`, `src/i18n`. Kết quả 13 tệp / 191 test, EXIT 0.
- Độ phủ:
  - Tổng (verify-1): 89,9 % dòng, 88,15 % nhánh. Cổng AppFront chấm theo ngưỡng tầng R-48 (domain 90, lib 80) và đã đạt. `src/lib/offline` đạt 91,98 % dòng, 90,42 % nhánh.
  - Từng tệp đổi (đo tại chỗ, dòng/nhánh):
    - `markerCommands.ts` 100/100
    - `queueStore.ts` 89,63/85,39
    - `replayer.ts` 98,34/92,55
    - `floorUploadGateway.ts` 96,26/80
    - `ConnectionStates.container.tsx` 88,29/76,47
    - `connectionStatesGateway.ts` 100/71,42
    - `versionHistoryFixtures.ts` 97,35/92,47
  - Mọi dòng **mới** đều được phủ, gồm `queueStore.ts:75-126, 403-428`, `floorUploadGateway.ts:211-212, 241-286` và `ConnectionStates.container.tsx:92-95`. Dòng chưa phủ đều có từ trước: các nhánh `catch` của IndexedDB/memory, `:271-273`, nhánh `cancelled` của container.

## Kiểm theo khối [9]/[12] (`DEBT-04/chung.md`)
- `git diff e0a9ec08..HEAD | grep -nE '^\+.*(TODO|FIXME|ponytail:|\.skip\(|\.fixme\(|waitForTimeout|@ts-ignore|@ts-expect-error|eslint-disable|it\.only)'` cho EXIT 1, tức rỗng.
- Diff không chạm tệp thuộc [12]: `src/lib/schemas/**`, `src/routes/**`, `vendor/**`, `eslint-rules/**`, ngưỡng `vitest.config.ts`, `playwright*.config.ts`, `.github/**`.
- 6 commit FIX và 2 merge đều đúng mẫu Conventional Commits, dòng đầu ≤ 72 ký tự, đủ `Prompt:`, `Fix:`, `Debt-Prompt: DEBT-04`.
- K27: mỗi commit chỉ chạm tệp của một chủ:
  - `vi.json` là F-05a;
  - `src/lib/offline/**` và FloorUploadScreen là F-03;
  - VersionHistory là F-08;
  - ConnectionStates không có chủ.
- Không đổi hợp đồng FE–BE. Lệnh `uploadDrawing` thêm trường `sessionId`, nhưng lệnh này chỉ sống ở IndexedDB phía FE.

## Soát theo trọng tâm cụm O

| Câu hỏi | Kết luận | Bằng chứng |
|---|---|---|
| Khoá có được cấp trước khi ghi lệnh không? | Đúng. | `floorUploadGateway.ts:241-243` gọi `await holdTabSession(...)` trước `addPendingCommand`. `holdTabSession` (`markerCommands.ts:57-79`) chỉ resolve trong callback đã cấp khoá, hoặc khi xin khoá hỏng. Lỗi khi xin khoá chỉ dẫn tới đếm thiếu, không mất tệp. Chưa có test ghim thứ tự này, xem #2. |
| Khoá có được query sau khi đọc danh sách lệnh không? | Đúng. | `floorUploadGateway.ts:269` (`listPendingCommands`) chạy trước `:277` (`readLiveTabSessions`), nên một lệnh đã có trong danh sách thì tab ghi nó đã giữ khoá. `query()` của Web Locks trả khoá của mọi client cùng origin. Mỗi lượt dọn chỉ query một lần (P-10). |
| BroadcastChannel hay người nghe có rò không? | Không rò. | `queueStore.ts:110-126` mở kênh khi có người nghe đầu tiên và đóng khi người cuối huỷ. Huỷ hai lần bị chặn bằng `delete()===false`. Khi không có người nghe, kênh tạm mở rồi đóng ngay (`:91-101`); P-6 đã chạy thử trên Node 24 và thư vẫn tới. Kênh không nhận thư của chính nó, nên trong một tab không bị báo đôi. Mỗi người nghe chạy trong một microtask riêng, nên người ném lỗi không chặn người sau (`:87-89`). Vitest 2.0.3 dùng pool `forks`, nên kênh Node không bắc chéo giữa các tệp test. |
| `queueRevision` có gây vòng render vô hạn không? | Không. | `ConnectionStates.container.tsx:92-95, 135`: lượt đọc lại chỉ gọi `listPending`, một thao tác chỉ đọc nên không phát thông báo. Trong `createQueueStore` chỉ `add`/`delete`/`moveToDeadLetter` được bọc `notifyingWrite` (`queueStore.ts:423-427`). Container không ghi; replayer không nghe. `isLoading` không bị bật lại nên không nhấp nháy. Gateway được `useMemo` theo prop. |
| Không có Web Locks thì sao? | Trình duyệt không có Web Locks coi mọi phiên có mã là còn sống. Đây là cái giá đã nêu, nhưng chưa có dòng sổ. | `markerCommands.ts:18-20, 89-106`, `floorUploadGateway.ts:211` (`null` khác `undefined`, P-8). Test có ở `useFloorUploadScreen.test.ts` ("trình duyệt không có Web Locks…") và `markerCommands.test.ts`. Lệnh mồ côi tích luỹ được và chiếm trần `MAX_PENDING_COMMANDS = 200`. Ngữ cảnh không bảo mật (http không phải localhost) cũng không có `navigator.locks`. Xem #1. |
| IndexedDB lỗi thì sao? | Chịu được. | `notifyingWrite` chỉ báo khi `ok` (`queueStore.ts:404-414`); có test cho trường hợp `moveToDeadLetter(999)` không báo. `clearOrphanUploads` gặp list hỏng thì `return`. `enqueueOffline` gặp lỗi thì trả `null`, màn vẫn giữ tệp. `addPendingCommand`/`delete` của IndexedDB đợi `transactionDone` rồi mới trả, nên tab khác đọc lại sau thông báo luôn thấy dữ liệu đã commit. |
| Lệnh của bản dựng cũ không có `sessionId`? | Bị coi là mồ côi và gỡ, giống FIX-459. | `markerCommands.ts:104-105` dùng `typeof sessionId === 'string'`. Bài NO-392 (c) có từ trước vẫn xanh (P-17). Khoảng chuyển giao bản dựng được chấp nhận (P-12): chỉ đếm thiếu, không mất tệp. |
| Replayer bỏ qua dấu đếm | Đúng. | `replayer.ts:229-235` dùng `continue`: không gửi, không đưa vào dead-letter, không gỡ, vẫn đếm. Bài "skips uploadDrawing marker commands…" khẳng định cả bốn điều đó. Tệp `floorUploadGateway.ts` không còn bản sao `isUploadDrawingCommand`; cả hai nơi dùng hàm chung (R-07). |
| Phiên của chính tab | Hồi quy nhỏ, đã được chấp nhận (P-13). | Lệnh của mount trước trong cùng tab chỉ còn lại khi lượt `dropOffline` lúc rời màn (`useFloorUploadScreen.ts:398-412`) hỏng. |

Cụm D:
- NO-397: `vi.json` hạ chữ thường 9 giá trị đơn vị. Không còn giá trị nào chỉ là đơn vị viết hoa: grep `": "(Mm|Cm|M|M²|…)"` rỗng. Không test hay e2e nào tra theo chữ cũ. `vi.units.test.ts` ghim luật này cho toàn tệp.
- NO-398: `countsAgainstPrevious` lấy diff thật của mỗi hàng so với bản ngay trước. Test khẳng định đủ 5 hàng (v13 rỗng vì cùng ảnh chụp với v12; v12 là hai bản thêm). `totals` của vùng so sánh vẫn là `SAMPLE_DIFF_COUNTS` (v13→v14), đúng nghĩa.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | R-34 | Có năm nợ chưa có dòng trong `DEBT.md`; dòng cuối của sổ hiện là NO-404. (a) Mục "Nợ mới" 1 của `O/bao-cao.md`: không có Web Locks thì lệnh `uploadDrawing` của tab đã đóng không bao giờ bị gỡ, nên đếm thừa và chiếm trần 200 lệnh. Nợ này do chính FIX-461 sinh ra, nên theo khối [9] phải được ghi sổ, không chỉ để trong báo cáo. (b) Mục "Nợ mới" 3: mã chết ở `toDeadLetterReason`. (c) `pascal-viewer.spec.ts:631` (B-3) hỏng ở e2e-1 và e2e-3 của nhánh và cả trên base (`pascal-base.log`). `timeline.md:8` ghi "nợ mới DEBT-05" nhưng chưa thấy dòng sổ. (d) `auth/login.spec.ts:52` và (e) `v4v5/pipeline-graph.spec.ts:51` chập chờn dưới tải ở e2e-2. | `DEBT.md` (sau NO-404); `src/lib/offline/markerCommands.ts:18-20`; `src/lib/offline/replayer.ts:69-70`; `e2e/pascal-viewer.spec.ts:631`; `e2e/auth/login.spec.ts:52`; `e2e/v4v5/pipeline-graph.spec.ts:51` | Điều phối ghi đủ cột: (a) Nit/P3, F-03, hướng sửa là gỡ theo tuổi `createdAt` hoặc nhịp tim phiên; (b) Nit, F-03; (c)(d)(e) P3, chủ của từng spec, chuyển DEBT-05, kèm đường log. |
| 2 | P3 | TEST (R-35, CON) | Hai bất biến thứ tự của NO-400 chưa được test ghim. Bất biến thứ nhất là cấp khoá trước khi ghi lệnh (`floorUploadGateway.ts:243`); bất biến thứ hai là đọc lệnh trước khi query khoá (`:269` trước `:277`). Cả hai fake (`useFloorUploadScreen.test.ts` `createFakeLocks`, `markerCommands.test.ts`) gọi `held.add(name)` ngay trong phần đồng bộ của `request`. Vì vậy nếu bỏ `await` ở `:243` hoặc đảo `:269`/`:277`, mọi bài vẫn xanh: tab A đã giữ khoá từ lâu trước khi tab B mở màn. | `src/screens/upload/FloorUploadScreen/floorUploadGateway.ts:243, 269-277`; `useFloorUploadScreen.test.ts` (nhóm NO-400) | Thêm một bài dùng fake cấp khoá bằng deferred. Khẳng định: (i) chưa cấp thì `enqueueOffline` chưa ghi lệnh; (ii) `clearOrphanUploads` đọc snapshot khoá **sau** `listPendingCommands`, bằng cách đếm thứ tự gọi qua spy. Chạy đột biến hai chỗ trên để thấy bài đỏ. |
| 3 | Nit | R-07 (MNT) | `[V15, V14, V13, V12, V11]` chép lại thứ tự đã có ở `SAMPLE_HISTORY` (`:244-250`) và được dựng lại ở mỗi lần gọi. | `src/screens/export/VersionHistory/versionHistoryFixtures.ts:270` | Dùng `SAMPLE_HISTORY.map((entry) => entry.version)` và nâng lên hằng số cấp module. |
| 4 | Nit | MNT (chú thích lệch) | Chú thích nói mọi lệnh `uploadDrawing` còn trong hàng đợi lúc mở màn "là của phiên trước" và bị gỡ. Sau NO-400, chỉ lệnh của phiên đã chết mới bị gỡ. Chú thích đầu `floorUploadGateway.ts` đã sửa, còn chú thích trong hook thì chưa. | `src/screens/upload/FloorUploadScreen/useFloorUploadScreen.ts:386-389` | Sửa câu theo `floorUploadGateway.ts:26-29` và dẫn NO-400. |
| 5 | Nit | TEST | Nhánh `cancelled` (bỏ kết quả đọc cũ) chưa được phủ. Có `queueRevision`, nó trở thành chốt chính khi nhiều thông báo tới dồn dập và các lượt đọc về không theo thứ tự. | `src/screens/system/ConnectionStates/ConnectionStates.container.tsx:114-116` | Thêm bài dùng gateway giả: lượt đọc 1 về muộn sau lượt đọc 2, rồi khẳng định số hiển thị theo lượt 2. |

Ghi nhận, không phải finding:
- P-18: `ConnectionStatesContainer` và `createReplayer` chưa có nơi gọi sản phẩm. NO-401/402 là sửa phòng trước.
- P-13: hồi quy của phiên chính tab đã được chấp nhận và có lý do đứng được.

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
| MNT | 3% | 3 | 0,09 |

Tổng: 4,87 / 5

## PHÁN QUYẾT: APPROVE WITH COMMENTS
Không có P0 hay P1. Cổng `pnpm verify` đạt 7/7 với EXIT 0 trên đúng `bb058bf2`. Các bài e2e hỏng đều nằm ngoài vùng diff và đã được chứng minh có sẵn trên base hoặc chập chờn dưới tải.

Cụm O đúng thiết kế người dùng đã duyệt (sessionId + Web Locks):
- khoá được cấp trước khi ghi lệnh;
- khoá được query sau khi đọc danh sách lệnh;
- kênh đóng khi hết người nghe;
- không có vòng render;
- đường lùi chọn an toàn: đếm thừa thay vì gỡ oan.

Cụm D đúng và có test ghim cho cả tệp.

Điểm 4,87 theo ma trận là APPROVE. Tôi ghi **WITH COMMENTS** vì finding #1 (P2) phải có dòng sổ trước khi đóng đợt. Gộp `master` được khi:
- **(a)** `DEBT.md` có đủ các dòng của #1: (a) nợ do FIX-461 sinh ra, (b) mã chết ở `toDeadLetterReason`, (c) e2e B-3, (d)–(e) e2e login và pipeline-graph.
- **(b)** Sổ sách của điều phối đã xong:
  - `docs/fixes.md` có khối cho FIX-461…464, 481, 482. Lúc review, `grep` chỉ thấy tới FIX-460.
  - Các dòng NO-397, 398, 400, 401, 402 được đóng theo `fix-*.md` của D và O.

Finding #2 (P3) và các Nit #3–#5: sửa trong đợt này nếu rẻ, nếu không thì ghi dòng `DEBT.md` cho DEBT-05. Chúng không chặn merge.
