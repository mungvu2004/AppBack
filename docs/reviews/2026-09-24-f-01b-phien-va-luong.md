# Review merge `feature/f-01b-phien-va-luong` → `master` (AppFront)

- Ngày: 2026-09-24 · Reviewer: phiên `/merge-review` (worker Orca `task_ee0b4b5e4faf`)
- Commit đầu nhánh: `cd92d66de999` · Nền: `master` `0774abfd6e11` · merge-base = `0774abf` (không lệch nền)
- Phạm vi: 25 file, 7 commit, +2664 / −149
- Cây làm việc: sạch (`git status --porcelain` rỗng)
- Worktree soát độc lập: `C:/Users/mxuan/orca/workspaces/AppFront/f01b-review` (không đụng worktree của tác giả)

## Cổng — chạy độc lập, mã thoát THẬT

`pnpm verify` (log: `…/scratchpad/verify-branch.log`, dòng cuối `EXIT=0`)

| # | Bước | Kết quả |
|---|---|---|
| 1 | typecheck | đạt |
| 2 | lint (`--max-warnings 0`) | đạt |
| 3 | import vòng | đạt |
| 4 | test + độ phủ | **đạt — 334/334 file, 7056/7056 ca** |
| 5 | build | đạt |
| 6 | kích thước gói | đạt |
| 7 | độ dài file | đạt (343 file, 0 vượt trần 400) |

**Lượt chạy của tôi KHÔNG tái hiện được chỗ hỏng mà tác giả khai ở bước 4.** Tác giả báo
"test+độ phủ HỎNG vì chập chờn có sẵn của máy"; lượt độc lập này xanh toàn bộ, mã thoát 0.
Kết luận: chẩn đoán chập chờn của tác giả **đúng** — không có file nào đỏ do thiết kế, và
không có finding P1 nào phát sinh từ bước 4. Tác giả đã báo cáo trung thực (E.10: khai
"hỏng" chứ không khai "đạt" cho thứ mình đo thấy đỏ).

### Kích thước gói — đo lại, khớp con số tác giả khai

| Cổng | Đo | Trần |
|---|---|---|
| màn hình đầu tiên (chunk vào + nhập tĩnh) | 162,4 KiB | 175 |
| chunk JS lớn nhất | 162,4 KiB | 170 |
| chi phí thêm cho một màn | 257,3 KiB | 280 |
| tổng CSS | 10,9 KiB | 12 |
| *cảnh báo* tổng JS mọi chunk | 1062,8 KiB | 800 (cảnh báo có từ trước, không làm hỏng cổng) |

### Độ phủ — đo lại

| Gói / file | Dòng | Nhánh | Ngưỡng |
|---|---|---|---|
| `src/lib/auth` | 92,66 % | 85,88 % | `src/lib` 80 % |
| `src/lib/auth/bootstrap.ts` | 100 % | 100 % | — |
| `src/lib/auth/refresh.ts` | 94,93 % | 81,63 % | — |
| `src/lib/realtime/eventChannel.ts` | 97,98 % | 90,19 % | — |
| `src/routes` | 95,85 % | 90,58 % | — |
| `src/store/resetUserScopedState.ts` | 100 % | 100 % | — |
| `src/api/endpoints.ts` | 100 % | 97,29 % | — |

Không hạ ngưỡng, không `skip`/`only`/`todo`, không `@ts-ignore`, không `eslint-disable` trần.
Một `eslint-disable-next-line local/no-direct-set` ở `SessionBootstrap.test.tsx:133` có lý do
viết kèm (đưa store về trạng thái đầu trong test) — chấp nhận được.

### e2e — chạy độc lập

`pnpm e2e` → **13 đạt / 2 đỏ / 15**, `EXIT=1`. Khớp chính xác con số tác giả khai.
Hai bài đỏ (`viewer3d.spec.ts:461` P2, `:503` Q2) đỏ vì
`<div aria-hidden="true" class="pointer-events-auto fixed bg-bg-overlay">` của lớp phủ
`EditorTour` nuốt cú bấm — **đúng** nguyên nhân tác giả ghi, và **không** bài nào đỏ vì ảnh
chuẩn. Nợ này thuộc một prompt riêng (mục 4.10 bật bộ mẫu cho e2e); tôi xác nhận lý do đứng
vững và không tính nó là finding.

---

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | CON-01 | Hai `connect()` chạy song song sau một lượt gia hạn chậm; `EventSource` cũ bị bỏ rơi không đóng và trình duyệt tự nối lại nó mãi | `src/lib/realtime/eventChannel.ts:210-227`, `:165-171` | `closeCurrentSource()` ở đầu `connect()` |
| 2 | P2 | RES-03 | Chuỗi thử lại lỗi TẠM không có trần số lượt và không dừng khi phiên ẩn danh | `src/lib/auth/refresh.ts:244-252` | dừng khi `status === 'anonymous'`, hoặc đặt trần `transientAttempt` |
| 3 | P2 | LOG-06 | `PUBLIC_ROUTE_PATTERNS` hứa một điều mà `end: true` không giữ được cho route lời mời có tham số | `src/routes/paths.ts:180-184` + `SessionBootstrap.tsx:175` | mẫu tiền tố `/login/*`, kèm ca `/login/invitation/abc123` |
| 4 | P3 | LOG-02 | Sàn 30 s đẩy lượt gia hạn chủ động ra SAU hạn token khi TTL ≤ 60 s | `src/lib/auth/refresh.ts:182-184` | kẹp sàn dưới `remainingMs` |
| 5 | P3 | MNT-07 | `toApiUrl` và `resolveAuthUrl` **không** cùng hành vi, dù hai docblock chéo nhau khẳng định là bản sinh đôi | `src/api/endpoints.ts:34-45`, `src/lib/auth/bootstrap.ts:28-50` | một bảng đầu vào dùng chung chạy qua cả hai hàm |
| 6 | P3 | TEST-08 | `__resetAuthForTests()` không xoá `lastKnownUserId`; ba file test dùng nó mà không tự gọi hàm kia | `src/lib/auth/session.ts:334-338` | gọi `__resetLastKnownUserForTests()` trong `__resetAuthForTests()` |
| 7 | Nit | TEST-04 | Khẳng định lỏng trên một đồng hồ tất định | `src/lib/auth/__tests__/refresh.test.ts:466-467` | `toBe(n)` thay cho khoảng 2–5 |
| 8 | Nit | TEST-04 | Bài kiểm không kiểm được điều docblock hứa: 3 trong 14 khoá | `src/store/__tests__/resetUserScopedState.test.ts` | dựng danh sách từ ba `create*Slice` rồi so với `MACHINE_SCOPED_KEYS` |
| 9 | Nit | MNT-09 | Docblock mô tả một cơ chế không chạy | `src/screens/auth/AuthScreen/AuthScreen.container.tsx:48-51` | sửa câu chữ |

### [1] P1 · CON-01 — `EventSource` bị bỏ rơi khi lượt gia hạn về chậm hơn lượt lùi

**Bằng chứng trong diff.** `onerror` (`eventChannel.ts:210`) gọi `scheduleReconnect()` ở dòng
215 — hẹn giờ 4 000 ms ở lỗi thứ ba (`backoff.ts:1`, `BASE_DELAYS_MS[2]`) — **rồi mới** gọi
`refreshAuth()` ở dòng 218. Callback thành công làm:

```ts
(ok) => { if (!ok || closed) return; clearReconnectTimer(); connect(); }
```

Nếu `refreshAuth()` giải quyết `true` **sau** khi hẹn giờ đã nổ thì `reconnectTimer` đã là
`null`, `clearReconnectTimer()` là lệnh rỗng, và `connect()` chạy lần thứ hai. `connect()`
(`:165-171`) **không** đóng `source` cũ — nó chỉ gán đè `source = nextSource`. `EventSource`
của lượt trước ở lại: `close()` của handle (`:240`) chỉ đóng `source` hiện tại, nên nó sống
tới lúc rời trang và **trình duyệt tự nối lại nó mãi** theo cơ chế retry sẵn có của
`EventSource`. Sự kiện không bị nhân đôi (guard `source !== nextSource` chặn), nhưng kết nối
thì rò. Cộng dồn qua nhiều chuỗi lỗi sẽ chạm trần 6 kết nối/host của HTTP/1.1 và chặn mọi
request khác cùng origin.

**Điều kiện kích hoạt.** Lượt gia hạn mất hơn ~4 s rồi mới **thành công** — đúng tình huống mà
ba lỗi SSE liên tiếp báo hiệu: máy chủ chậm nhưng còn sống. `REFRESH_TIMEOUT_MS` là 15 s, nên
cửa sổ này rộng 11 s. (Lượt gia hạn hết giờ trả `false` và bị guard `!ok` chặn — chỉ lượt
thành-công-chậm mới rò.)

**Đây là hồi quy của nhánh này.** Trên `master` chỉ có MỘT đường gọi `connect()` — hẹn giờ lùi
— và lúc ấy `source` luôn đã là `null` nhờ `closeCurrentSource()` ở dòng 214. Nhánh này thêm
đường gọi thứ hai mà không thêm guard.

**Vì sao bộ test không bắt được.** `makeManualClock` (`eventChannel.test.ts:451`) chỉ chạy hẹn
giờ khi test gọi `flush()`, nên hai đường không bao giờ chồng nhau. Ca
`reconnects immediately when refreshAuth resolves true` (`:529`) giải quyết promise **trước**
khi flush; ca `only waits for the backoff when refreshAuth …` (`:549`) giải quyết rồi mới
flush. Không ca nào flush **giữa** lúc `refreshAuth` đang bay — đúng cái khe mà lỗi sống trong đó.

**Đề xuất.** Một dòng:

```ts
function connect(): void {
  if (closed) return;
  closeCurrentSource();          // ← thêm
  emit('dang-noi');
```

Kèm một ca: `failThrice(clock)` → `clock.flush()` → `resolveRefresh(true)` → khẳng định
`MockEventSource.instances` có **4** chứ không 5, và thực thể thứ ba đã đóng.

### [2] P2 · RES-03 — chuỗi thử lại lỗi tạm không có trần, và không biết phiên đã ẩn danh

`handleTransientFailure` (`refresh.ts:244-252`) luôn hẹn lượt sau. `resolveRetryDelayMs`
(`bootstrap.ts:112-119`) kẹp **khoảng chờ** trong [1 s, 60 s] nhưng không kẹp **số lượt**, và
hàm không hỏi `getSessionState().status`.

Hệ quả đo được: một khách **chưa đăng nhập** mở `/login` lúc máy chủ chết. `startAppSession()`
chạy ở mọi lượt tải trang kể cả đường công khai (`SessionBootstrap.tsx:222` — effect không
phụ thuộc `isPublic`), gặp 502, và từ đó bắn `POST /auth/refresh` mỗi 60 giây **vô hạn** cho
một phiên không tồn tại. Nhân với số khách trong một sự cố là một đàn request đập vào chính
máy chủ đang hồi phục. `scheduleRefreshFromSession` có kiểm `isDocumentHidden()`
(`refresh.ts:172`); `handleTransientFailure` thì không, nên thẻ chạy nền cũng bắn.

Prompt yêu cầu "retry có trần và backoff" — *khoảng chờ* có trần, *số lượt* thì không.

**Đề xuất.** Dừng chuỗi khi `getSessionState().status === 'anonymous'`, hoặc đặt trần cho
`transientAttempt` rồi để `visibilitychange` / nút "thử lại" của `SessionGate` khởi động lại.

### [3] P2 · LOG-06 — `end: true` không giữ được lời hứa của `PUBLIC_ROUTE_PATTERNS`

`paths.ts:175-184` ghi: *"Một hằng ở đây không dựng ra route nào — nó chỉ nói 'nếu đường này
tồn tại thì nó công khai'"*, và liệt kê `/login/invitation`, `/login/reset-password`. Nhưng
`matchesPublicRoute` so bằng `matchPath({ path, end: true }, pathname)`
(`SessionBootstrap.tsx:175`). Route lời mời thật gần như chắc chắn mang tham số
(`/login/invitation/:token`), và `end: true` **không** khớp nó — người bấm link mời sẽ bị
`<Navigate>` đá về `/login?next=…` thay vì thấy màn nhận lời mời.

Hôm nay chưa nổ: `ROUTE_PATTERNS` mới chỉ có `login: '/login'`, hai route kia chưa tồn tại.
Nên đây là **bẫy chờ F-09a**, không phải lỗi đang chạy. Tôi vẫn để P2 vì nó nằm đúng chỗ một
ghi chú tự tin khẳng định là đã lo xong, và người của F-09a sẽ mất thời gian dò lại.

**Đề xuất.** Một mẫu tiền tố (`'/login'` với `end: false`, hoặc `'/login/*'`) kèm một ca cho
`/login/invitation/abc123`.

### [4] P3 · LOG-02 — sàn 30 s đẩy lượt gia hạn ra sau hạn token khi TTL ≤ 60 s

`scheduleRefreshFromSession` (`refresh.ts:182-184`):

```ts
const floorMs = lastRefreshAttemptAt === null ? 0 : REFRESH_MIN_INTERVAL_MS - (now - lastRefreshAttemptAt);
const delayMs = Math.max(remainingMs - REFRESH_LEAD_TIME_MS, floorMs, 0);
```

Với TTL 30 s: `remainingMs - 60_000` âm, `floorMs ≈ 30 000`, nên lượt gia hạn nổ **đúng lúc**
token hết hạn chứ không trước. Lượt ấy thường vẫn đi được vì nó dựa vào cookie chứ không vào
token; nhưng nếu máy chủ trả 401 thì `createRefreshFailure()` (`:236`) phát `signed-out` sang
**mọi thẻ** — đúng cái F-01b tồn tại để tránh.

Ca `caps a fast clock at five refreshes across two fake minutes` (`refresh.test.ts:445`) chạy
đúng cấu hình TTL 30 s này, nhưng chỉ khẳng định số lượt nằm trong khoảng 2–5; nó không
khẳng định token còn sống ở mỗi lượt, nên nó không phát hiện được chỗ này.

### [5] P3 · MNT-07 — `toApiUrl` và `resolveAuthUrl` không cùng hành vi

Đây là câu hỏi số 8 của đề bài, và câu trả lời là **lệch**. Đo bằng Node trên cùng bộ đầu vào:

| Đầu vào | `toApiUrl` | `resolveAuthUrl` |
|---|---|---|
| `('http://h/api', '/streams/x?since=5')` | `http://h/api/streams/x%3Fsince=5` | `http://h/api/streams/x?since=5` |
| `('http://h/api', '/streams/x#frag')` | `http://h/api/streams/x%23frag` | `http://h/api/streams/x#frag` |
| `path = 'ws://x/y'` | ghép bậy thành `http://h/api/ws://x/y` | trả nguyên `ws://x/y` |

Ba nguồn lệch:

1. **Nhận diện URL tuyệt đối.** `resolveAuthUrl` dùng `/^[a-z][a-z0-9+.-]*:/i`
   (`bootstrap.ts:12`) — mọi scheme. `toApiUrl` dùng `/^https?:/i` (`endpoints.ts:35`).
2. **Query và fragment.** `toApiUrl` gán `base.pathname = …` (`endpoints.ts:42`); setter
   `pathname` của WHATWG URL mã hoá `?` thành `%3F` và `#` thành `%23`. `resolveAuthUrl` dựng
   qua `new URL(suffix, base.origin)` (`bootstrap.ts:38`) nên hai ký tự ấy được phân tích đúng.
3. (nhỏ) `resolveAuthUrl` đi qua `base.origin` nên bỏ phần `user:pass@` của base; `toApiUrl` giữ.

**Hôm nay chưa nổ**, và lý do đáng ghi lại: `ENDPOINTS.streams.*` trả đường trần không query,
còn `appendLastEventId` (`eventChannel.ts:70-81`) ghép `?lastEventId=` **sau** `toApiUrl` bằng
`URL.searchParams`. Nên quyết định giữ hai bản riêng (để `src/lib/auth` không nhập `src/api`,
CLAUDE.md 0.4) là **đúng** và tôi không đề nghị gộp. Vấn đề là hai docblock chéo nhau nói
"sửa một bên thì đọc bên kia" mà không nói hai bên đang khác nhau ở đâu — người đọc sẽ tưởng
chúng tương đương.

**Đề xuất.** Một bảng đầu vào dùng chung chạy qua cả hai hàm và khẳng định cùng kết quả (bảng
đặt ở file test nào cũng được — file test không tạo đường nhập giữa hai tầng sản phẩm).

### [6] P3 · TEST-08 — `lastKnownUserId` rò qua ranh giới test

`__resetAuthForTests()` (`session.ts:334-338`) gọi `resetAuthEvents / resetRefreshState /
resetAuthState`; không cái nào chạm `lastKnownUserId` (`bootstrap.ts:66`). Hàm
`__resetLastKnownUserForTests()` có tồn tại và **được** bốn nơi gọi
(`refresh.test.ts:158,177`, `eventChannel.test.ts:608,616`, `SessionBootstrap.test.tsx:353`)
— nhưng ba file khác gọi `__resetAuthForTests()` mà không gọi nó:
`src/api/__tests__/appClient.test.ts`, `src/lib/auth/__tests__/session.test.ts`,
`src/screens/auth/AuthScreen/AuthScreen.test.tsx`. File cuối có dựng phiên thật với một
`user.id`, nên id ấy ở lại trong bộ nhớ module cho bất cứ thứ gì chạy sau trong cùng worker.

Các ca "đổi người" hiện xanh vì chúng tự dựng đủ hai lượt trong cùng một bài. Nhưng đây đúng
loại phụ thuộc thứ tự chạy mà bước 4 của cổng đang mang tiếng chập chờn — đáng dọn.

### Nit

- **[7]** `refresh.test.ts:466-467` dùng `toBeGreaterThan(1)` + `toBeLessThanOrEqual(5)`. Đồng
  hồ giả và `fetch` giả đều tất định nên con số đếm được chính xác; `toBe(n)` mới bắt được
  hồi quy của sàn 30 s.
- **[8]** `resetUserScopedState.test.ts` chỉ chạm 3 trong 14 khoá (`zoom`, `theme`,
  `activeTool`), trong khi giá trị của thiết kế "danh sách GIỮ" nằm ở chỗ nó phải **khớp đủ**
  ba slice. Tôi đã đối chiếu tay: 5 khoá `viewSlice` + 6 `uiSlice` + 3 `toolSlice` = **đúng
  14**, khớp `MACHINE_SCOPED_KEYS`, không thừa không thiếu. Một ca dựng danh sách từ chính ba
  `create*Slice` sẽ giữ được điều đó mà không cần ai đối chiếu tay lần nữa.
- **[9]** `AuthScreen.container.tsx:48-51` nói `configureAppSession()` được gọi lại "để tiêm
  chuyến đi riêng khi có". Không đúng: `ensureAuthConfigured` (`sessionSetup.ts:50-52`) thoát
  sớm khi `isAuthConfigured()`, và từ lượt này `SessionBootstrap` luôn cấu hình trước ở lúc
  tải trang — nên `fetchImpl` truyền vào đây **luôn bị bỏ qua** trên đường chạy thật. Vô hại
  (dưới cờ mock thì `sessionSetup` tự chọn đúng chuyến đi ấy), nhưng câu chữ mô tả một cơ chế
  không chạy.

---

## Tám chỗ đề bài yêu cầu soi — trả lời

1. **Phân loại ba nhánh lỗi (`refresh.ts`).** Không ca nào lọt sai nhánh. 408/429/≥500 →
   tạm; 401 → phát mọi thẻ; mọi 4xx khác và thân W16 đọc không ra → chỉ thẻ này. 3xx không
   tới được vì `fetch` mặc định `redirect: 'follow'`. Nhánh `catch` xếp đúng thứ tự:
   `timedOut || TypeError` → tạm, rồi `signal.aborted` → không đổi trạng thái, rồi mới
   `endSessionLocally()`. **Cờ `timedOut` KHÔNG rò giữa hai lượt**: nó là `let` khai bên trong
   callback truyền cho `refreshSingleFlightRunner`, mỗi lượt một closure mới, và `timeoutId`
   bị `clearTimeout` trong `finally`. Lệnh huỷ do đăng xuất
   (`cancelActiveRequests` → `createAbortReason`) tạo `Error` có `name = 'AbortError'`, không
   phải `TypeError`, nên nó rơi đúng vào nhánh 2 — có ca riêng
   (`stops without touching the session when sign-out aborts the refresh`).
2. **Sàn 30 s.** Bốn ca miễn trừ (401, `bootstrap`, `broadcast`, SSE) **đi thẳng được**, vì
   sàn chỉ được `scheduleRefreshFromSession` đọc và bốn ca ấy gọi `refreshSingleFlight()` trực
   tiếp. Lượt thử lại sau lỗi tạm cũng không đọc sàn (nó dùng `resolveRetryDelayMs`). Không
   đường nào bị hoãn oan. Chỗ lệch khỏi prompt này **đứng vững**. Ngoại lệ duy nhất là finding [4].
3. **Đổi người.** `clearQueryCache` → `clearUserData` → `setAuthenticatedSession` giữ đúng thứ
   tự ở **mọi** nguồn kể cả lượt do `signed-in` của thẻ khác, vì cả bốn nguồn đi qua đúng một
   thân hàm; có ca riêng (`clears when another tab announces a different user`).
   `lastKnownUserId` cập nhật ở đúng một chỗ, chỉ khi id mới khác `null` — đúng, vì giữ id cũ
   qua lúc ẩn danh chính là điều kiện để lượt đăng nhập sau phát hiện được đổi người. Không có
   chỗ nào quên cập nhật nó trên đường chạy thật; chỗ quên nằm ở tầng test (finding [6]).
4. **`SessionGate` năm nhánh.** Hai bất biến **giữ được**.
   (a) `<Fragment key={userId ?? ''}>` đứng ở **cùng một vị trí** trong cây ở cả hai nhánh
   có-dải và không-dải, và React đối chiếu theo `key` trong mảng con nên phần tử `null` phía
   trước không đẩy nó — màn con không gắn lại khi dải bật/tắt. Có ca riêng
   (`vẫn vẽ màn con, và bật rồi tắt dải KHÔNG gắn lại màn`).
   (b) Nhánh `isPublic` trả `<>{children}</>`, **không** `key`. Có ca riêng
   (`KHÔNG gắn lại màn /login đang nháy thành công khi phiên mở ra`).
   Ghi chú nhỏ: `SessionBootstrap` ghi vào `useRef` **trong lượt vẽ** (`:203-210`). Về kỹ
   thuật đây là thứ React gọi là không an toàn dưới chế độ đồng thời; ở đây nó bất biến qua
   hai lượt vẽ của StrictMode và giá trị chỉ dùng làm gợi ý `state.notice`, nên tôi không
   tính là finding.
5. **Ngân sách gói.** `SessionBootstrap.tsx` nhập tĩnh đúng năm thứ:
   `react`, `react-router-dom`, `@/components/feedback/InlineAlert`,
   `@/components/feedback/Skeleton`, `@/lib/auth/state`, cộng một `import type`. **Không** thứ
   nào kéo `zod` hay `@/lib/http` vào chunk vào. `./sessionSetup` nạp bằng `import()` động ở
   hai chỗ (`:216`, `:230`). Cổng đo lại: chunk vào 162,4 / 175 KiB, còn dư 12,6 KiB. Lý do
   không dùng `useSession` **đứng vững** và đã được đo.
6. **`MACHINE_SCOPED_KEYS`.** Đúng và đủ: 14 khoá, khớp chính xác 5 + 6 + 3 khoá dữ liệu của
   `viewSlice` / `uiSlice` / `toolSlice`. Không khoá dữ liệu nào của người cũ sót lại — mọi
   khoá của bảy slice còn lại rơi vào nhánh xoá, và lịch sử hoàn tác bị `clear()`. Hướng
   "danh sách GIỮ" là lựa chọn đúng và docblock giải thích đúng lý do.
7. **`eventChannel` — bộ đếm và `close()`.** Bộ đếm reset đúng ở `onopen` (`:176`), có ca
   riêng (`starts a new chain after an open`). `close()` giữa lúc đang gia hạn **không** nối
   lại nhầm — guard `closed` ở `:221`, có ca riêng. Nhưng xem finding [1] cho chỗ thứ ba mà
   không ca nào chạm tới.
8. **Hai hàm ghép đường.** **Lệch** — xem finding [5]. Quyết định giữ hai bản riêng là đúng
   và tôi không đề nghị gộp; chỗ cần sửa là làm cho hai bản thật sự cùng hành vi, hoặc nói ra
   chúng khác nhau ở đâu.

## Kiểm lại số tác giả khai

| Tác giả khai | Tôi đo | Phán quyết |
|---|---|---|
| bảy bước: 4 hỏng vì chập chờn, sáu bước kia đạt | **bảy bước đều đạt**, `EXIT=0`, 7056/7056 | chẩn đoán chập chờn **đúng**; không có file nào đỏ do thiết kế |
| chunk vào 162,4 / 175 | 162,4 / 175 | khớp |
| chunk lớn nhất 162,4 / 170 · một màn 257,3 / 280 · CSS 10,9 / 12 | khớp cả ba | khớp |
| tổng JS 1062,8 / 800 là cảnh báo có từ trước | khớp | khớp |
| `lib/auth` 92,45 / 85,02 | 92,66 / 85,88 | khớp trong sai số giữa hai lượt |
| `eventChannel.ts` 97,98 / 87,23 | 97,98 / 90,19 | khớp (nhánh cao hơn) |
| `routes` 94,05 / 88,57 · `resetUserScopedState.ts` 100 / 100 | 95,85 / 90,58 · 100 / 100 | khớp |
| e2e 13 đạt / 2 đỏ, không bài nào đỏ vì ảnh chuẩn | 13 / 2, đỏ vì lớp phủ tour chặn click | khớp |
| `router.tsx` 324 · `SessionBootstrap.tsx` 235 dòng nội dung | bước 7 đạt, 0 file vượt 400 | khớp |

Tác giả khai số trung thực. Không thấy một chỗ nào báo "đạt" cho bước chưa chạy (E.10).

## Chỗ lệch khỏi prompt — lý do có đứng vững không

| # | Chỗ lệch | Phán quyết |
|---|---|---|
| 1 | `SessionSnapshot.serverUnreachable` tuỳ chọn | **đứng vững**. Bắt buộc cả hai làm `tsc` đỏ ở một file khối [9] cấm sửa; lúc chạy trường này luôn có mặt vì mọi bản chụp do `state.ts` dựng và nó luôn ghi; mọi nơi đọc đều viết `=== true`. Đã kiểm ba nơi đọc ở `SessionGate` — cả ba dùng `=== true` |
| 2 | Sàn 30 s đặt trong `scheduleRefreshFromSession` | **đứng vững** (xem câu 2 ở trên). Ngoại lệ: finding [4] |
| 3 | `SessionBootstrap.test.tsx` dùng `MemoryRouter` | **đứng vững**. Chữa cách khác phải sửa `vitest.setup.ts`, file prompt cấm chạm. 23 ca vẫn phủ được năm nhánh của cổng |
| 4 | `processingGateway.ts` thêm hai dòng `import` | **đứng vững**. Hai dòng ấy là `resolveApiBaseUrl` và `toApiUrl`, không dùng thì không ghép được đường S1 |
| 5 | Route gốc không dùng `useSession` | **đứng vững và đã đo** (xem câu 5) |

## Chỗ làm tốt, ghi lại để không ai "dọn" nhầm

- **Đường SSE khớp hợp đồng chính xác.** `ENDPOINTS.streams.notifications()` và
  `.uploadProgress()` ghép ra đúng S1 và S2 của `docs/charter/BE-BIND.md:74-75` và đúng hai
  đường trong `openapi.json`. Bản trên `master` (`/api/streams/notifications` viết cứng) chỉ
  chạy khi API cùng origin; bản này ghép qua `resolveApiBaseUrl()` nên chạy cả khi khác origin.
- **`createProgressStream` cố ý KHÔNG nhận `refreshAuth`, và đó là đúng.** Nó tự rơi sang
  quay vòng qua `fetchEvents` → `client.drawings.progress` → `authHttp`, tức đã có đường xử
  lý 401 riêng. Chỉ kênh thông báo (không có đường dự phòng) mới cần `refreshAuth`. Sự bất
  đối xứng này là thiết kế, không phải chỗ thiếu.
- **Không có bão broadcast.** `broadcastAuthIntent('signed-in')` chỉ phát khi
  `(options.source ?? 'local') === 'local'`, nên lượt gia hạn do broadcast kích hoạt không
  phát lại. Mở N thẻ không sinh vòng lặp.
- **Bộ mẫu thông báo không bị cắt cụt.** Ba chuỗi `message` trong `__mocks__/client.ts` trông
  như câu dở ("phát hiện 1 vi phạm luật ở") nhưng chúng là **tiền tố** ghép với `objectLabel`
  ngay sau — đọc ra "phát hiện 1 vi phạm luật ở trục a-3". Đúng, không phải hồi quy.
- **Bảy commit đều đúng Conventional Commits và đều có trailer `Prompt: F-01b`.** Thân commit
  ghi rõ chỗ lệch khỏi prompt và lý do — dễ soát.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 0,15 | 5,0 | 0,75 |
| CON — trạng thái dùng chung, tranh chấp | 0,20 | 3,0 | 0,60 |
| RES — timeout, retry có trần | 0,15 | 3,0 | 0,45 |
| LOG — ca biên | 0,15 | 4,0 | 0,60 |
| API / hợp đồng | 0,10 | 5,0 | 0,50 |
| TEST | 0,15 | 4,0 | 0,60 |
| OBS / MNT | 0,10 | 5,0 | 0,50 |

**Tổng: 4,00 / 5**

## PHÁN QUYẾT: REQUEST CHANGES

Nhánh này làm đúng việc nó nhận và làm kỹ: cổng bảy bước xanh trong lượt chạy độc lập của
tôi (tác giả còn báo cáo *dưới* thực tế), đường SSE khớp chính xác hợp đồng BE-BIND, năm chỗ
lệch khỏi prompt đều có lý do đứng vững và đã được đo, và các docblock giải thích *vì sao*
chứ không chỉ *cái gì*. Điểm 4,00 phản ánh chất lượng ấy.

Chặn merge vì đúng **một** finding P1: `src/lib/realtime/eventChannel.ts` để rò một
`EventSource` mỗi lần lượt gia hạn về chậm hơn lượt lùi, và cái bị rò là một kết nối SSE tự
nối lại mãi — cộng dồn thì chạm trần 6 kết nối/host và chặn mọi request khác cùng origin. Đây
là hồi quy do nhánh này tạo ra (trên `master` chỉ có một đường gọi `connect()`), và bộ test
không bắt được vì đồng hồ giả của nó làm hai đường không bao giờ chồng nhau.

**Phải sửa trước khi gộp vào `master`:**

1. **[1] P1** — `closeCurrentSource()` ở đầu `connect()` (`eventChannel.ts:165`), kèm một ca
   flush hẹn giờ **trước** khi `refreshAuth` giải quyết.

**Nên sửa trong cùng lượt (hai món, rẻ, cùng vùng mã):**

2. **[2] P2** — cho chuỗi thử lại lỗi tạm một điều kiện dừng khi phiên ẩn danh.
3. **[3] P2** — mẫu tiền tố cho `/login/*`, để link lời mời của F-09a không bị cổng đá về.

Ba finding P3 và ba Nit không chặn merge; ghi vào `DEBT.md` hoặc cuốn vào prompt sau, tuỳ
người duyệt. Hai bài e2e đỏ là nợ đã ghi của một prompt riêng — tôi đã chạy lại và xác nhận
đúng nguyên nhân tác giả nêu, không tính là finding.
