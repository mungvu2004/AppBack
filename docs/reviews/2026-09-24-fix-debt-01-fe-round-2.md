# Phán quyết review lượt 2 — AppFront `fix/debt-01-fe` (vòng sửa FIX-097)

**Ngày:** 2026-09-24 · **Prompt:** DEBT-01 (việc T5, vòng sửa 1) · **Reviewer:** độc lập (không phải tác giả, không phải người điều phối)
**Nhánh:** `fix/debt-01-fe` @ `8cc0095815b0f9eba5c2923acc3f8a5a90714c9e` · **Phạm vi:** `git diff 70f614e..8cc0095` (1 commit: `src/lib/realtime/eventChannel.ts` + test)
**Worktree review:** `C:/Users/mxuan/orca/workspaces/AppFront/review-debt-01-fe-r2` — `git status --porcelain` rỗng trước và sau
**Lượt 1:** `docs/reviews/2026-09-24-fix-debt-01-fe.md`

## PHÁN QUYẾT: REQUEST CHANGES

F-1, F-3, F-4, F-6 của lượt 1 **đã sửa đúng như đề xuất**. Nhưng chính việc nối kênh SSE vào
`refreshSingleFlight` đã đưa vào một **hồi quy P1**: khi luồng SSE rớt vì mạng chập hoặc vì BE
khởi động lại, lượt refresh đi kèm cũng hỏng. Tầng auth coi mọi lần refresh hỏng là phiên đã
chết, nên **đăng xuất người dùng ở mọi thẻ**. F-2 (bão refresh) **chưa hết**: chốt ở tầng auth
chỉ chặn khi refresh hỏng, không chặn khi refresh thành công mà luồng vẫn chết. Việc chờ
refresh (F-3) lại tạo thêm một điểm treo không có hạn giờ. **NO-154 chưa đóng được.**

Tôi nói rõ: đề xuất ở F-1 lượt 1 ("mặc định thành `refreshSingleFlight`") **bỏ sót** nhánh
`catch → createRefreshFailure` của hàm đó. Tác giả làm đúng theo đề xuất; lỗi nằm ở đề xuất.

---

## 1. Bảng E.10 — từ mã thoát THẬT

Lệnh: `pnpm install --frozen-lockfile && pnpm verify`, chạy một lượt trong RUNNER.
Log: `backend/dieu-phoi/chay/DEBT-01/r5r2-verify.log`, dòng cuối `EXIT=1`.

| Bước | Việc | Trạng thái | Nguồn mã thoát |
|---|---|---|---|
| 1 | typecheck | **đạt** | `pnpm verify` |
| 2 | lint | **đạt** | `pnpm verify` |
| 3 | import vòng | **đạt** | `pnpm verify` (`lib/realtime → lib/auth` không tạo vòng) |
| 4 | test + độ phủ | **HỎNG**: 8 test hỏng / 6921, 7/329 file; `EXIT=1` | `pnpm verify` |
| 5 | build | **đạt**: chạy tay `pnpm build`, `EXIT=0` | `r5r2-build.log` |
| 6 | kích thước gói | **đạt**: chạy tay `pnpm size`, `EXIT=0` (cảnh báo tổng JS 1062/800 KiB, không chặn, có từ trước) | `r5r2-size.log` |
| 7 | độ dài file | **đạt**: chạy tay `pnpm length`, `EXIT=0` (0 file vượt 400) | `r5r2-length.log` |

`pnpm verify` **thoát 1**. Bước 5–7 **không chạy trong `pnpm verify`** (cổng dừng ở bước 4).
Tôi chạy tay từng bước theo `scripts/verify.mjs:49-64`, mã thoát ghi ở trên.

### 1.1. Tám test hỏng ở bước 4 là flake dưới tải, không do diff

| Phép đo | Kết quả |
|---|---|
| `pnpm verify`, 329 file song song (244 s) | 7 file đỏ: `ModelLibrary` (2 test), `ExportPanel`, `VersionHistory`, `RuleReport`, `RuleSettings`, `PropertyInspector`, `Viewer3DPanels`. Sáu lỗi là `Test timed out in 5000ms`, một lỗi là `findBy`/`LAZY_WAIT` hết hạn khi DOM còn ở skeleton, một lỗi là `expected 1 to be greater than 1` |
| Chạy riêng đúng 7 file đó, cùng một lượt | 6/7 qua. Còn **1** đỏ (`Viewer3DPanels` [VP-1], DOM còn skeleton), `EXIT=1` (`r5r2-rerun7.log`) |
| `Viewer3DPanels.test.tsx` chạy riêng 3 lượt | **3/3 qua, 12/12**, `EXIT=0` (`r5r2-vp.log`) |
| So với lượt 1 | Tập file đỏ **khác hẳn**. Lượt 1: `RuleReport`, `UserManagement`, `Viewer3DPanels`, `MobileViewer.container`, `Viewer3DOverlays`, `routes/router` |
| Liên hệ với diff | Không file nào trong 7 file nhập `realtime`, `lib/auth` hay `eventChannel` (`grep` rỗng). `eventChannel.test.ts` 26/26 qua ngay trong lượt đỏ |

Tập đỏ đổi giữa các lượt và co dần khi giảm tải. Vì vậy đây là flake theo tải, **không phải
hồi quy**. Thân commit `944981b` (F-01a) cũng ghi `master` `9cf0b0b` đỏ 12 ca trong cùng kiểu
đo.

### 1.2. Độ phủ file bị chạm

`pnpm exec vitest run src/lib/realtime src/screens/system/NotificationCenter --coverage --coverage.include=src/lib/realtime/eventChannel.ts`
→ `EXIT=0`, 5 file / 71 test (`r5r2-cov.log`).

| File | % Dòng | % Nhánh | % Hàm | Dòng chưa phủ | Ngưỡng `src/lib` ≥ 80 |
|---|---|---|---|---|---|
| `src/lib/realtime/eventChannel.ts` | 98 | 93,75 | 84,21 | 92–94 (`catch` của `appendLastEventId`, có từ trước) | ✅ |

Số đo **khớp** báo cáo tác giả.

---

## 2. Kiểm lại từng finding lượt 1

| Finding lượt 1 | Kết quả lượt 2 | Bằng chứng |
|---|---|---|
| F-1 (P1) đường refresh thứ hai, vứt token | ✅ **Đã sửa.** `defaultRefreshAuth` gọi `refreshSingleFlight` (`eventChannel.ts:22-24`). Token mới vào phiên qua `setAuthenticatedSession` (`refresh.ts:248`), URL theo `config.baseUrl` (`refresh.ts:234`). **Nhưng nó sinh ra R2-1** | đọc mã; probe "ok": `status=authenticated` sau refresh |
| F-2 (P2) bão refresh khi `progressStream` dựng lại kênh | ❌ **Chưa hết.** Chỉ chặn được ca refresh hỏng vĩnh viễn. Xem R2-2 | probe: **29 POST / 30 phút** với 1 luồng, 87 POST với 3 luồng |
| F-3 (P3) không chờ refresh trước lần nối kế | ✅ **Đã sửa** (`eventChannel.ts:241-246`), có test thứ tự (`eventChannel.test.ts:311`). **Nhưng nó sinh ra R2-3** | test F-3 xanh; probe "hang" |
| F-4 (P3) promise bị reject rơi | ✅ **Đã sửa**: `.catch(() => undefined)` (`:242`), có test (`eventChannel.test.ts:332`) | test xanh, không có unhandled rejection |
| F-6 (P3) test bắn `fetch` thật | ✅ **Đã sửa**: `makeChannel`/`makeNotificationChannel` mặc định `refreshAuth: vi.fn()` (`:95`, `:432`), cộng `vi.mock('@/lib/auth')` cho cả file (`:17`). Các file test khác dùng mặc định cũng không bắn mạng, vì auth chưa cấu hình (xem R2-4) | probe "unconfigured": `globalFetchCalls=0` |
| F-7 (Nit) kiểm hợp đồng refresh | ⚠️ **Một phần.** Chỉ khẳng định rằng `refreshSingleFlight` giả được gọi (`:520`). Spec T5r1 đòi khẳng định URL/POST/credentials. Xem R2-5 | đọc test |
| F-9 / F-10 (Nit) | ⚠️ Nợ flake đã được khai trong báo cáo. Bảng E.10 của vòng sửa vẫn ghi hàng 4 là "ĐẠT — phạm vi việc mình" | `bao-cao-t5-fe.md:235` |

### 2.1. Probe tự dựng (file tạm, đã xoá; `git status --porcelain` rỗng)

Tôi đặt file `src/lib/realtime/__tests__/zzReviewProbe.test.ts` rồi xoá sau khi chạy. Cách dựng:
`configureAuth({ baseUrl, fetchImpl })` với `fetchImpl` giả, `bootstrapSession()` để có phiên
`authenticated`, sau đó đếm số POST `/auth/refresh`. `EventSource` giả báo lỗi ngay sau mỗi
lần dựng, nên luồng chết suốt thời gian đo. Đồng hồ giả chạy 30 phút. Kênh dùng
`refreshAuth` **mặc định**, tức đường thật tới `refreshSingleFlight`.

| Kịch bản | POST refresh | Trạng thái phiên sau đó | Ghi chú |
|---|---|---|---|
| Refresh **thành công**, 1 `progressStream`, luồng chết 30 phút | **29** | authenticated | 87 `EventSource`, 686 lượt poll: bão vẫn còn, khoảng 1 POST/phút |
| Như trên, **3** `progressStream` | **87** | authenticated | single-flight không gộp được vì các lượt refresh không chồng lên nhau |
| Refresh trả **401** (hỏng vĩnh viễn) | 1 | anonymous | chốt `refreshFailed` giữ đúng; đăng xuất ở đây là đúng |
| Refresh **lỗi mạng** (`TypeError: Failed to fetch`) | 1 | **anonymous** | **R2-1**: mạng chập làm người dùng bị đăng xuất |
| Refresh trả **502** (BE đang khởi động lại) | 1 | **anonymous** | **R2-1**: triển khai BE làm người dùng bị đăng xuất |
| Refresh **treo** (promise không bao giờ giải quyết) | 1 | — | **R2-3**: kênh đứng ở `dang-noi` suốt 30 phút, không dựng lại lần nào, `progressStream` **không** chuyển sang poll (0 lượt poll) |
| **Chưa `configureAuth`** (tải lại trang, chưa qua `AuthScreen`) | **0** | — | **R2-4**: refresh mặc định im lặng không làm gì |

---

## 3. Finding

### R2-1 · **P1** · LOG/RES · Lỗi SSE thoáng qua làm người dùng bị đăng xuất ở mọi thẻ

`src/lib/realtime/eventChannel.ts:22-24, 237-246` ↔ `src/lib/auth/refresh.ts:233-267, 178-189`

`refreshSingleFlight` bắt **mọi** lỗi trong `catch` (`refresh.ts:264-266`): `TypeError` mạng,
`!response.ok` với 5xx, và `AbortError`. Tất cả đều đi vào `createRefreshFailure()`. Hàm này
gọi `endAnonymousSession({ refreshFailed: true })` rồi `broadcastAuthIntent('signed-out')`,
tức **đăng xuất ở thẻ này và mọi thẻ khác**, đồng thời bật chốt `refreshFailed` chặn mọi lần
refresh về sau.

Trước commit này, nhánh `catch` đó chỉ chạy khi REST nhận 401 (`client.ts:436`) hoặc khi hẹn
giờ refresh chủ động tới lượt. Cả hai lúc đó đều có lý do tin rằng phiên đang có vấn đề. Commit
`8cc0095` thêm một nguồn gọi mới là `onerror` của `EventSource`. Nguồn này bắn **đúng vào lúc
mạng hoặc BE đang hỏng**: BE khởi động lại (nginx trả 502), Wi-Fi đổi mạng, máy thức dậy sau
khi ngủ. Lượt refresh đi kèm gần như chắc chắn hỏng theo, và phiên bị huỷ.

**Bằng chứng:** probe "network" và "502" ở bảng 2.1 cho thấy `status=anonymous` sau đúng 1
POST. Trên `master` (chưa có refresh) và trên `70f614e` (hàm riêng nuốt lỗi), cùng tình huống
đó **không** đăng xuất ai.

**Tác động:** `NotificationCenter` giữ một kênh SSE suốt phiên. Vì vậy **mỗi lần triển khai
hoặc khởi động lại BE sẽ đăng xuất mọi người dùng đang mở ứng dụng**, và mỗi lần mạng chập
cũng vậy. Thay đổi đang tự lưu (A7) có thể rơi vào khoảng phiên đã bị huỷ. Hậu quả này nặng
hơn chính NO-154 (P3) mà commit muốn chữa.

**Đề xuất (sửa tại gốc, nơi mọi người gọi cùng đi qua):** trong `refresh.ts`, chỉ gọi
`createRefreshFailure()` khi máy chủ **từ chối dứt khoát** (response 401/403). Lỗi tạm thời
(`TypeError`, `AbortError` do hạn giờ, 5xx, 429) thì trả `false` mà **không** huỷ phiên và
không bật `refreshFailed`. Kèm hai test:

1. Kênh SSE lỗi, refresh gặp `TypeError` hoặc 502 → phiên vẫn `authenticated`, `refreshFailed`
   vẫn `false`.
2. Refresh gặp 401 → đăng xuất như cũ.

Cách này cũng chữa luôn ca hẹn giờ refresh chủ động gặp mạng chập, một lỗi có sẵn cùng dạng.
`src/lib/auth/refresh.ts` **nằm ngoài whitelist T5**, nên người điều phối cần nới whitelist
hoặc giao FIX cho chủ của `src/lib/auth` (K27). Nếu không nới được, phương án tạm là kênh SSE
**không** dùng `refreshSingleFlight` làm mặc định cho tới khi `refresh.ts` phân biệt được lỗi
tạm với lỗi dứt khoát.

### R2-2 · **P2** · RES · F-2 chưa hết: refresh thành công mà luồng vẫn chết thì bão vẫn còn

`src/lib/realtime/eventChannel.ts:11-20, 130, 237` ↔ `src/lib/realtime/progressStream.ts:141-151, 184-219`

Theo docblock (`:14-18`), single-flight ở tầng auth là "chỗ chốt 'một chuỗi lỗi một refresh'
của F-2". **Điều này sai.** `createSingleFlight` (`src/lib/http/singleFlight.ts`) chỉ gộp các
lượt gọi **đang bay cùng lúc**, và xoá khoá ngay khi lượt gọi xong. Còn `refreshFailed` chỉ bật
khi refresh **hỏng**. Trong khi đó chốt theo chuỗi vẫn là `refreshedForErrorChain`, một biến
cục bộ của từng lần gọi `createEventChannel` (`:130`). Mỗi 60 s `progressStream` dựng một kênh
mới (`progressStream.ts:151 → 184 → 194`), và kênh mới lại refresh.

**Bằng chứng:** probe cho **29 POST / 30 phút** với một luồng và **87** với ba luồng, khớp con
số "~30 lượt" mà lượt 1 dự báo. Spec T5r1 đòi riêng một test ("dựng lại kênh nhiều lần với lỗi
liên tiếp → số lần refresh bị chặn"). **Test đó không có.** Báo cáo ghi lý do là "không cần bài
kiểm riêng".

**Đề xuất:** đặt chốt ngoài closure. Ví dụ: một mốc `lastSseRefreshAt` ở cấp module trong
`eventChannel.ts`, bỏ qua refresh nếu mốc còn trong khoảng tối thiểu (chẳng hạn 5 phút), hoặc
chỉ gỡ mốc khi **có** kênh `onopen` thành công. Kèm test dùng `createProgressStream` với luồng
chết 30 phút, khẳng định số POST ≤ trần đã chọn. Sửa lại docblock `:14-18` cho đúng.

### R2-3 · **P2** · RES · Chờ refresh mà không có hạn giờ: refresh treo thì kênh chết hẳn, không rơi về poll

`src/lib/realtime/eventChannel.ts:241-246`

`scheduleReconnect()` chỉ chạy trong `.finally()` của `refreshAuth()`. `refreshSingleFlight`
gọi `fetchImpl` chỉ với `signal: getRequestAbortSignal()` (`refresh.ts:240`). Tín hiệu này chỉ
huỷ khi đăng xuất, **không có hạn giờ**. Nếu POST treo (kết nối TCP hỏng sau khi đổi mạng, hay
proxy giữ kết nối), thì:

- kênh không bao giờ xếp lịch nối lại và không phát `mat-ket-noi`;
- `progressStream` không đếm được `sseFailures`, nên **không bao giờ** chuyển sang poll (`progressStream.ts:219`);
- vì refresh dùng single-flight, lượt treo đó còn chặn **mọi** lượt refresh khác trong ứng dụng, kể cả đường REST 401.

**Bằng chứng:** probe "hang" ở bảng 2.1. Sau 30 phút: `channelStates=dang-noi`, chỉ 2
`EventSource` (mỗi kênh dựng đúng 1 lần), 0 lượt poll. Trên `70f614e` (dùng `void`) việc nối
lại không phụ thuộc vào refresh. Test F-3 mới (`eventChannel.test.ts:311`) chỉ kiểm ca refresh
**có** giải quyết.

**Đề xuất:** cho `refreshAuth()` đua với một hạn giờ, chẳng hạn bằng `backoff.nextDelayMs()`
hoặc một hằng ≤ 10 s, rồi mới gọi `scheduleReconnect()`. Kèm test: refresh không bao giờ giải
quyết → `EventSource` thứ hai vẫn được dựng sau hạn giờ cộng độ trễ, và `progressStream` vẫn
rơi về poll.

### R2-4 · **P3** · LOG · Trước khi `configureAuth()` chạy, refresh mặc định im lặng không làm gì

`src/lib/realtime/eventChannel.ts:22-24` ↔ `src/lib/auth/state.ts:65-67` ↔ `src/screens/auth/AuthScreen/AuthScreen.container.tsx:172-177`

Chỉ `AuthScreen` gọi `configureAuth()`, và chỉ ngay trước lượt post đăng nhập. Tôi `grep` cả
`8cc0095` lẫn `944981b` và không thấy lời gọi nào trong `src/main.tsx`, dù docblock
`appClient.ts` của `944981b` viết rằng "`configureAuth()` chạy ở `src/main.tsx`". Sau khi người
dùng tải lại trang, `refreshSingleFlight` ném `Auth is not configured`, và lỗi bị `.catch` nuốt.
Kết quả là FIX-097 **không làm gì** (probe "unconfigured": 0 lượt fetch). Bản `70f614e` vẫn
refresh được trong ca này.

Đây là nợ có sẵn của phần khởi động ứng dụng, không phải lỗi mới của diff. Nhưng nó khiến
NO-154 vẫn còn nguyên sau mỗi lần tải lại trang. **Đề xuất:** mở dòng nợ cho chủ vỏ ứng dụng
(`configureAuth` lúc khởi động), đồng thời sửa câu sai trong docblock `appClient.ts`. Finding
này không chặn riêng.

### R2-5 · **Nit** · TEST · F-7 chỉ khẳng định rằng hàm giả được gọi

`src/lib/realtime/__tests__/eventChannel.test.ts:17, 520-549`

`vi.mock('@/lib/auth')` thay cả module. Test chỉ kiểm được rằng mặc định gọi
`refreshSingleFlight`, còn URL, `POST` và `credentials` như spec T5r1 yêu cầu thì không được
khẳng định. Phần hợp đồng đó đã có test ở `src/lib/auth/__tests__/session.test.ts`, nên mức ở
đây là Nit. Khi sửa R2-1, test tích hợp (auth thật cộng `fetchImpl` giả, như probe ở 2.1) sẽ
phủ luôn phần này.

### R2-6 · **Nit** · E.10 · Báo cáo tác giả

- `bao-cao-t5-fe.md:235`: hàng 4 bảng E.10 vẫn ghi "ĐẠT — phạm vi việc mình" (F-9 lặp lại). Theo E.10, trạng thái phải là "chưa chạy" với cổng đầy đủ.
- `bao-cao-t5-fe.md:219`: báo cáo ghi F-2 "tự đóng theo F-1" mà không có phép đo nào. Probe ở 2.1 cho thấy điều đó không đúng.

---

## 4. Những gì ĐẠT

- **F-1, F-3, F-4, F-6 cài đặt đúng đề xuất.** Test mới tái hiện đúng thứ cần chặn: dựng
  `EventSource` thứ hai trước khi refresh xong, và promise bị reject rơi ra ngoài.
- **Kỷ luật commit:** 1 commit, dòng đầu `fix(realtime): …` dài 70 ký tự. Trailer `Prompt:
  F-01b`, `Fix: FIX-097`, `Co-Authored-By` liền khối. Diff chỉ gồm 2 file trong whitelist.
- **Test cũ không bị nới:** các chỗ thêm `await vi.advanceTimersByTimeAsync(0)` chỉ nhường một
  nhịp microtask cho bước `.finally()`. Không assert nào bị bỏ hay đổi giá trị.
- **Ranh giới import:** `lib → lib`, bước import vòng đạt.

### 4.1. Tiền đề `master` của `F:/AppFront` — KHÔNG còn là `9cf0b0b`

`git -C F:/AppFront log -1 master` = **`944981b`** `feat(transport): keep /api, lazy token,
bare auth, code-based errors`, trailer `Prompt: F-01a`, commit lúc 20:28 hôm nay. Reflog cho
thấy `master@{0}: commit`, còn `origin/master` vẫn là `9cf0b0b`, tức **chưa đẩy lên remote**.
Commit này thuộc **prompt khác (F-01a)**, không phải tác giả nhánh này, và không đụng file nào
của nhánh. `git merge-tree 944981b 8cc0095` **gộp sạch**. Người điều phối cần biết chuyện này
trước khi gộp. Tôi không đánh giá `944981b`.

---

## 5. Nợ

| NO | FIX | **Phán quyết reviewer** | Lý do |
|---|---|---|---|
| NO-086 | FIX-099 | ✅ đóng được khi merge (giữ nguyên lượt 1) | không đụng trong vòng sửa |
| NO-099 | FIX-098 | ✅ đóng được khi merge (giữ nguyên lượt 1) | không đụng trong vòng sửa |
| NO-154 | FIX-097 | ❌ **CHƯA đóng được** | Kênh thông báo đã có refresh và token mới được đọc vào phiên. Nhưng (a) lỗi tạm thời làm người dùng bị đăng xuất (R2-1, P1); (b) `progressStream` vẫn refresh khoảng 1 lượt/phút khi luồng chết (R2-2); (c) refresh treo làm kênh chết hẳn (R2-3); (d) sau khi tải lại trang thì refresh không làm gì (R2-4) |

### 5.1. Flake có chặn gộp không? (luật E.10 của AppFront)

E.10 (`F:/AppFront/CLAUDE.md:132`, `scripts/verify.mjs:14`) **không cho phép** ghi bước 4 là
"đạt". Cổng của nhánh này là **HỎNG**, và khối [11] mục 1 ("`pnpm verify` thoát 0") **chưa
đạt**. Nhưng E.10 là luật về **báo cáo trung thực**, không phải luật chọn cách gộp. Mục 1.1 đã
chứng minh cả tám ca đỏ không do diff, và `master` cũng đỏ theo cùng kiểu.

Kết luận của tôi: **flake không phải lý do chặn nhánh này**, với điều kiện (1) có dòng nợ bên
dưới và (2) người điều phối ghi rõ lời miễn cổng trong lần gộp ("bước 4 HỎNG do NO-flake,
không do diff"), chứ không ghi "đạt". Lần này nhánh vẫn bị chặn, nhưng là do **R2-1 (P1)**.

### 5.2. Nợ MỚI (đề nghị người điều phối mở dòng; tôi không sửa `DEBT.md`)

1. **Bộ test AppFront flake dưới tải, `pnpm verify` bước 4 không xanh một cách tất định** · P2
   · chủ: người giữ bộ test màn hình AppFront. Tập đỏ đổi theo từng lượt:
   - lượt 1: `RuleReport`, `UserManagement`, `Viewer3DPanels`, `MobileViewer.container`, `Viewer3DOverlays`, `routes/router`;
   - lượt 2: `ModelLibrary`, `ExportPanel`, `VersionHistory`, `RuleReport`, `RuleSettings`, `PropertyInspector`, `Viewer3DPanels`.

   Kiểu lỗi: `Test timed out in 5000ms` / `findBy*` hoặc `LAZY_WAIT` hết hạn khi DOM còn ở
   skeleton của `import()` lười. Chạy riêng thì xanh. `master` `9cf0b0b` đỏ 12 ca (thân commit
   `944981b`). Hướng sửa: nâng hạn chờ đồng loạt cho các bài chờ `import()` lười (mẫu
   `LAZY_WAIT` ở `Viewer3DPanels.test.tsx:163`), hoặc hạ `maxWorkers` của vitest trong
   `verify`. Không retry và không hạ ngưỡng (K24).
2. **`configureAuth()` chỉ chạy lúc đăng nhập (R2-4)** · P3 · chủ: vỏ ứng dụng / chủ
   `src/lib/auth`. Sau khi tải lại trang, mọi đường gọi `refreshSingleFlight` ném lỗi và bị nuốt.
   Docblock `appClient.ts` (từ `944981b`) viết sai rằng `main.tsx` có cấu hình.
3. **`refreshSingleFlight` coi lỗi tạm thời như phiên chết (gốc của R2-1)** · P1 nếu FIX-097
   gộp nguyên trạng, nếu không thì P2 (vẫn còn ở ca hẹn giờ refresh chủ động) · chủ:
   `src/lib/auth/refresh.ts`. Mở dòng này nếu R2-1 không được sửa ngay trong vòng tới.

---

## 6. Việc phải làm để chuyển thành APPROVE

| # | Việc | Mức |
|---|---|---|
| 1 | R2-1: lỗi tạm thời của refresh (mạng, 5xx, hết hạn giờ) không được đăng xuất phiên. Sửa gốc ở `refresh.ts` (cần nới whitelist hoặc giao FIX cho chủ) kèm hai test | P1 |
| 2 | R2-2: chốt refresh nằm ngoài từng kênh, có trần theo thời gian, kèm test `progressStream` với luồng chết 30 phút; sửa docblock `eventChannel.ts:14-18` | P2 |
| 3 | R2-3: có hạn giờ cho lượt chờ refresh trước lần nối kế, kèm test refresh treo | P2 |
| 4 | R2-4: mở dòng nợ (không đòi sửa trong vòng này) | P3 |
| 5 | R2-5 / R2-6: test tích hợp auth thật khi làm #1; sửa hàng 4 bảng E.10 của báo cáo | Nit |

FIX-098 và FIX-099 **giữ nguyên, không đụng**.

---

## 7. Lệnh và nhật ký để soát lại

Các log nằm trong `F:/AppBack/backend/dieu-phoi/chay/DEBT-01/`. Mã thoát thật là dòng `EXIT=`
cuối mỗi log.

| Việc | Lệnh | Mã thoát | Log |
|---|---|---|---|
| Cổng đầy đủ | `pnpm install --frozen-lockfile && pnpm verify` | `EXIT=1` (dừng ở bước 4) | `r5r2-verify.log` |
| 7 file đỏ, chạy riêng một lượt | `pnpm exec vitest run <7 file>` | `EXIT=1`, 1/110 đỏ (`Viewer3DPanels`) | `r5r2-rerun7.log` |
| `Viewer3DPanels` chạy riêng ×3 | `pnpm exec vitest run …Viewer3DPanels.test.tsx` | `EXIT=0`, 3 × 12/12 | `r5r2-vp.log` |
| Bước 5 chạy tay | `pnpm build` | `EXIT=0` | `r5r2-build.log` |
| Bước 6 chạy tay | `pnpm size` | `EXIT=0` | `r5r2-size.log` |
| Bước 7 chạy tay | `pnpm length` | `EXIT=0` | `r5r2-length.log` |
| Độ phủ `eventChannel.ts` | `pnpm exec vitest run src/lib/realtime src/screens/system/NotificationCenter --coverage …` | `EXIT=0`, 71/71 | `r5r2-cov.log` |
| Probe R2-1..R2-4 (file tạm, đã xoá) | `pnpm exec vitest run src/lib/realtime/__tests__/zzReviewProbe.test.ts` | các số liệu ở bảng 2.1 | stdout phiên review |
| Gộp thử với `master` mới | `git merge-tree --write-tree 944981b 8cc0095` | sạch | — |

**Lệch khỏi quy trình:** lệnh `runner.sh run` đầu tiên được gõ vào pane RUNNER lúc pane còn
đang chạy verify AppBack của một phiên khác (hai phiên dùng chung handle), nên dòng lệnh bị
nuốt và log rỗng. Tôi chạy lại lúc 20:55 khi pane đã rảnh. `pnpm verify` **chỉ chạy một lượt
tính kết quả**.
