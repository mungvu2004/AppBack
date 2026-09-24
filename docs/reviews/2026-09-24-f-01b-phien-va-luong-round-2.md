# Review merge lượt 2 — `feature/f-01b-phien-va-luong` → `master` (AppFront)

- Ngày: 2026-09-24 · Reviewer: phiên `/merge-review` (worker Orca `task_7e6c8617536f`)
- Lượt 1: `docs/reviews/2026-09-24-f-01b-phien-va-luong.md`, commit `6691e00`, `REQUEST CHANGES`, 1 P1 + 2 P2 + 3 P3 + 3 Nit
- Sha mới: `dd27f78f3958` · trước sửa `cd92d66de999` · nền vẫn `master` `0774abfd6e11`
- Phạm vi lượt này: **chỉ** `git diff cd92d66..dd27f78` — 12 file, 1 commit, +380 / −18
- Cây làm việc: sạch

---

## Cổng — chạy độc lập

`pnpm verify` (log `…/scratchpad/verify-r2.log`, dòng cuối `EXIT=0`)

| # | Bước | Kết quả |
|---|---|---|
| 1–7 | typecheck · lint · import vòng · test+độ phủ · build · kích thước gói · độ dài file | **cả bảy đạt** |

- **335/335 file, 7074/7074 ca.** (Tác giả khai 7073 — lệch một ca, không đáng kể.)
- Kích thước gói: 162,4/175 · 162,4/170 · 257,3/280 · CSS 10,9/12 · tổng JS 1062,7/800 (cảnh báo cũ). Khớp con số tác giả khai, và **không đổi so với lượt 1**.
- `pnpm e2e`: **13 đạt / 2 đỏ**, đúng hai bài nợ có tên cũ — `viewer3d.spec.ts:479` (P2) và `:521` (Q2). Không bài nào đỏ thêm, không bài nào đỏ vì ảnh chuẩn. Khớp.

### Độ phủ — đo lại, TĂNG dù vừa thêm ba nhánh mới

| File | Dòng | Nhánh | Lượt 1 |
|---|---|---|---|
| `src/lib/auth` | 92,74 % | 86,05 % | 92,66 / 85,88 |
| `src/lib/auth/refresh.ts` | 95,08 % | 82,17 % | 94,93 / 81,63 |
| `src/lib/auth/bootstrap.ts` | 100 % | 100 % | 100 / 100 |
| `src/api/endpoints.ts` | **100 %** | **100 %** | 100 / 97,29 |
| `src/lib/realtime/eventChannel.ts` | 98,00 % | 90,19 % | 97,98 / 90,19 |
| `src/routes` | 95,85 % | 90,58 % | không đổi |

Không `skip`/`only`/`todo`, không hạ ngưỡng, không `@ts-ignore`.

---

## Sáu finding và ba Nit của lượt 1 — trạng thái

| # | Lượt 1 | Trạng thái | Ghi chú |
|---|---|---|---|
| [1] | **P1** CON-01 | ✅ **ĐÃ SỬA ĐÚNG** | xem dưới |
| [2] | P2 RES-03 | ✅ đã sửa | kèm một Nit về câu chữ và một P3 |
| [3] | P2 LOG-06 | ✅ **ĐÃ SỬA ĐÚNG** | |
| [4] | P3 LOG-02 | ⚠️ **đã sửa, nhưng mở ra một hồi quy mới** | xem P2-A |
| [5] | P3 MNT-07 | ✅ **sửa tốt hơn tôi đề xuất** | |
| [6] | P3 TEST-08 | ✅ đã sửa | |
| [7][8][9] | Nit | ✅ cả ba | [8] đáng khen riêng |

### [1] P1 CON-01 — đóng đúng, và ca test đúng là ca bắt được lỗi

`closeCurrentSource()` đặt ở đầu `connect()` (`eventChannel.ts:168-178`) là lời sửa tôi đề nghị, và nó **an toàn với mọi người gọi có sẵn**: trên đường lùi, `source` đã là `null` do `onerror` gọi `closeCurrentSource()` trước đó, nên dòng mới là lệnh rỗng; ở lượt `connect()` đầu tiên `source` cũng là `null`. Không đường nào đổi hành vi, đúng một đường hết rò.

Ca mới (`eventChannel.test.ts:579-614`) làm đúng chỗ tôi nói bộ test cũ bỏ trống: nó `flush()` hẹn giờ lùi **trước** rồi mới `resolveRefresh(true)` — khe 11 giây thật. Và nó đếm **kết nối còn sống** chứ không đếm số lần dựng (`instances.filter((s) => !s.closed)`), rồi khẳng định thêm `instances[afterBackoff - 1].closed === true`. Đó chính là hình dạng của lỗi: số lần dựng vẫn đúng, thứ rò ra là cái không ai đóng. Gỡ dòng sửa ra thì ca này đỏ với hai kết nối sống — tác giả khai đã kiểm chứng, và cấu trúc ca cho thấy khẳng định ấy đứng vững.

### [3] P2 LOG-06 — `/*` là lời sửa đúng, và ca test khoá đúng lời hứa

`'/login/invitation/*'` và `'/login/reset-password/*'`, `/login` giữ trần. Docblock mới nói rõ vì sao hai đường sau mang `/*` còn đường đầu thì không, và nói thẳng F-09a phải làm gì (đặt route dưới đúng hai tiền tố ấy) và khi nào phải sửa bảng. Ca mới (`SessionBootstrap.test.tsx:393-415`) dựng route `/login/invitation/:token` thật rồi render ở `/login/invitation/abc123`, khẳng định màn đăng nhập hiện ra, `screenMounts === 0`, và đường trên màn vẫn là `/login/invitation/abc123` chứ không bị `<Navigate>` đổi. Khoá đúng lời hứa.

### [5] P3 MNT-07 — gộp hành vi thay vì ghi nợ, đúng hướng hơn đề xuất của tôi

Tôi đề nghị "một bảng dùng chung khẳng định cùng kết quả"; tác giả làm bảng **và** đưa `toApiUrl` về đúng thuật toán của `resolveAuthUrl`, nên bảng ấy không còn là chỗ ghi lại sự lệch mà là chỗ chặn nó quay lại. Đã kiểm ba chỗ lệch cũ:

| đầu vào | nay |
|---|---|
| `('http://h/api', '/streams/x?since=5')` | hai hàm cùng ra `http://h/api/streams/x?since=5` |
| `('http://h/api', '/streams/x#frag')` | cùng ra `…/streams/x#frag` |
| `path = 'ws://x/y'` | cùng trả nguyên `ws://x/y` |

`toApiUrl` bỏ `base.pathname = …`/`base.search = ''`/`base.hash = ''` và chuyển sang `new URL(suffix, base.origin)` — đúng đường mà setter `pathname` không còn tham gia, nên `%3F`/`%23` biến mất. Regex scheme về cùng một biểu thức. `endpoints.ts` lên **100 % dòng / 100 % nhánh**.

**Bảng 12 ca có bỏ sót gì không?** Tôi soát lại ba nguồn lệch tôi nêu ở lượt 1: scheme (ca `scheme khác http`), query (ca `giữ query`), fragment (ca `giữ fragment`) — đủ cả ba. Ca thứ ba tôi nêu — base mang `user:pass@` — **không** có trong bảng; nhưng nó đã hết lệch một cách tự nhiên, vì `toApiUrl` nay cũng đi qua `base.origin` như `resolveAuthUrl` (và `origin` bỏ userinfo ở cả hai bên). Đây là chỗ hai bản *cùng* bỏ userinfo, tức cùng hành vi — không phải chỗ lệch. Không đáng thêm ca.

Ca cuối (`khớp nhau trên mọi ca của bảng, không chỉ khớp giá trị mong đợi`) là một chi tiết tốt: nếu ai đó sửa cả `expected` lẫn một hàm mà quên hàm kia, ca 1 đỏ; nếu ai đó sửa cả hai hàm theo cùng một hướng sai, ca 1 đỏ. Hai ca cùng nhau khoá được cả "đúng giá trị" lẫn "bằng nhau".

### Nit [8] — đáng khen riêng

Danh sách GIỮ nay **suy ra từ chính ba factory** `createViewSlice`/`createUiSlice`/`createToolSlice` và khoá `toHaveLength(14)`, rồi so từng khoá trước/sau. Ai thêm một khoá vào `uiSlice` mà quên `MACHINE_SCOPED_KEYS` sẽ làm ca này đỏ ngay. Đây đúng là thứ tôi nói "đối chiếu tay một lần là đủ cho hôm nay và vô dụng cho lần sau".

---

## Finding MỚI của lượt 2

| # | Mức | ID | Mô tả | Vị trí |
|---|---|---|---|---|
| A | **P2** | RES-04 | Sàn 30 s bị vô hiệu **hoàn toàn** khi `remainingMs` tiến về 0 → vòng lặp gia hạn không trần, không chịu trần 8 lượt của [2] | `src/lib/auth/refresh.ts:199-220` |
| B | P3 | RES-05 | `transientAttempt` không reset trên hai đường "khởi động lại" mà docblock nêu — mỗi lần chỉ được đúng MỘT lượt, không phải một thang mới | `refresh.ts:283-301` + `refresh.test.ts:369-389` |
| C | Nit | MNT-09 | Docblock của `handleTransientFailure` gán công cho nhánh sai | `refresh.ts:285-292` |
| D | — | *quan sát, có từ trước, ngoài phạm vi lượt 2* | `resolveExpiresAt` dựng `expiresAt` từ đồng hồ **cục bộ** khi thân trả `expiresIn`, nhưng `remainingMs` lại trừ `serverOffsetMs` | `refresh.ts` |

### [A] P2 · RES-04 — công thức mới mất sàn ở chính chỗ nó cần nhất

**Đây là chỗ đề bài bảo tôi soi kỹ nhất, và lập luận của tác giả đúng ở phần chính nhưng hụt một bước.**

Công thức mới:

```ts
const idealMs      = Math.max(remainingMs - REFRESH_LEAD_TIME_MS, 0);
const latestSafeMs = Math.max(Math.floor(remainingMs / 2), 0);
const delayMs      = Math.max(idealMs, Math.min(floorMs, latestSafeMs));
```

`Math.min(floorMs, latestSafeMs)` làm sàn **co giãn theo quãng đời còn lại**. Đó chính là ý tưởng, và nó đúng cho TTL ngắn. Nhưng khi `remainingMs` tiến về 0 thì `latestSafeMs` tiến về 0, và sàn không còn gì để chặn. Đo bằng chính hai công thức:

| `remainingMs` | delay MỚI | delay CŨ |
|---|---|---|
| 600 000 | 540 000 | 540 000 |
| 120 000 | 60 000 | 60 000 |
| 60 000 | 30 000 | 30 000 |
| 30 000 | **15 000** | 30 000 ← đúng chỗ [4] sửa |
| 1 000 | **500** | 30 000 |
| 0 | **0** | 30 000 |
| −510 000 | **0** | 30 000 |

**Kiểm chứng chạy thật (A/B).** Tôi dựng một bài tạm: `fetchImpl` trả W16 **thành công** với `expiresAt` bằng đúng tiêu đề `Date` của chính phản hồi (tức `remainingMs = 0` sau khi trừ lệch), rồi đếm số lượt gia hạn trong 1 giây giả.

```
mã hiện tại (dd27f78)        → lượt gia hạn trong 1 giây giả = 18
chỉ thay 1 dòng về công thức cũ → lượt gia hạn trong 1 giây giả = 0
```

Bài tạm đã bị xoá; cây làm việc sạch, `HEAD` vẫn `dd27f78`.

**Vì sao trần 8 lượt của [2] KHÔNG cứu được chỗ này.** Trần ấy nằm trong `handleTransientFailure`, tức đường **lỗi**. Ở đây mỗi lượt gia hạn **thành công** — `transientAttempt` được đặt về 0 ở mỗi lượt thành công — nên vòng lặp này đi hoàn toàn ngoài trần, và không có gì khác chặn nó. 18 lượt trong một giây giả là tốc độ của đồng hồ giả; với mạng thật nó là một request mỗi vòng round-trip, mỗi thẻ, mãi mãi.

**Đường tới được.** Cần `remainingMs ≲ 0` trên một lượt **thành công**. Ba cách:
1. BE trả `expiresAt` bằng hoặc trước tiêu đề `Date` của chính nó (lỗi BE, hoặc `ACCESS_TOKEN_TTL_S` đặt rất thấp — `AuthSettings` cho phép `ge=1`).
2. Tiêu đề `Date` vắng hoặc không đọc được — `resolveServerOffsetMs` trả 0 — **và** đồng hồ máy khách nhanh hơn TTL. Chính file này có một hằng số và một docblock dành riêng cho kịch bản "đồng hồ nhanh chín phút"; nhanh hơn mười phút là quá kịch bản ấy đúng một phút.
3. `ACCESS_TOKEN_TTL_S` đặt 1 s → delay 500 ms → 120 request/phút/thẻ.

Không cách nào xảy ra ở một triển khai đúng (BE mặc định TTL 600 s, `Date` luôn có). Nhưng cả ba đều biến **lỗi của người khác** thành một cú tự đập vào mình — đúng cái lớp vấn đề mà chính tác giả đã công nhận khi nhận sửa [2] ("một thẻ trình duyệt đập vào chính máy chủ đang hồi phục, nhân với số người đang mở trang thì chuỗi ấy tự nó thành một sự cố thứ hai"). Nguyên tắc ấy đúng ở `handleTransientFailure` thì cũng đúng ở đây.

**Và chú thích đang khẳng định điều ngược lại.** Khối bình luận mới viết: *"vẫn chặn được vòng lặp gia hạn liên tục mà sàn sinh ra để chặn"*. Câu ấy **sai ở đúng biên** — và chặn vòng lặp liên tục là lý do tồn tại của sàn. Một người đọc sau sẽ tin là vòng lặp không thể xảy ra.

**Đề xuất — một dòng, dùng lại hằng số đã có:**

```ts
const delayMs = Math.max(idealMs, Math.min(floorMs, latestSafeMs), RETRY_MIN_DELAY_MS);
```

`RETRY_MIN_DELAY_MS` (1 000) đã có sẵn ở `bootstrap.ts:109` — không sinh hằng thời lượng mới. Hệ quả: TTL 600 s không đổi (`idealMs` thắng), TTL 30 s không đổi (15 000 thắng), `remainingMs ≤ 0` cho 1 000 ms thay vì 0 — vẫn là "sớm nhất có thể một cách an toàn", nhưng không còn là vòng quay. Kèm một ca: một lượt **thành công** trả token đã chết không được sinh quá một nhúm lượt trong một giây.

### [B] P3 · RES-05 — "khởi động lại" chỉ cho đúng một lượt, không phải một thang mới

Sau khi trần 8 lượt nổ, `transientAttempt` đứng ở 8. Không đường nào trong hai đường mà docblock nêu đặt nó về 0: `scheduleRefreshFromSession` (đường `visibilitychange`) không chạm nó, `retryAppSession()` → `bootstrapSession()` cũng không. Nên mỗi lần quay lại thẻ, hoặc mỗi lần bấm "thử lại", người dùng được **đúng một lượt**: hoặc nó thành công, hoặc `handleTransientFailure` chạm `>= 8` ngay và im trở lại. Không có 1, 2, 4… lần nữa.

Hành vi ấy tự nó chấp nhận được — có thể còn tốt hơn một thang đầy đủ. Vấn đề là **cả docblock lẫn tên ca test đều nói khác**: `REFRESH_MAX_TRANSIENT_ATTEMPTS` viết "còn HAI đường khởi động lại", và ca mới tên là `restarts the ladder when the tab comes back into view` trong khi nó chỉ khẳng định `refreshCalls()` **lớn hơn** con số cũ — một lượt thêm là đủ để xanh. Ca không sai; tên ca và chú thích thì sai.

Đề xuất: hoặc đặt `transientAttempt = 0` khi `scheduleRefreshFromSession` hẹn lại sau một lượt bỏ cuộc (làm cho chú thích thành đúng, và một người quay lại thẻ sau bữa trưa xứng đáng có một thang mới), hoặc đổi tên ca và chú thích thành "cho thêm đúng một lượt".

### [C] Nit · MNT-09 — chú thích gán công cho nhánh sai

Docblock của `handleTransientFailure` nói nhánh `status === 'anonymous'` là thứ chặn kịch bản "khách chưa đăng nhập đứng ở `/login` lúc máy chủ chết". Trên đúng đường ấy trạng thái là **`unknown`**, không phải `anonymous`: một 502 là lỗi tạm, nó không đặt phiên về ẩn danh. Thứ thật sự dừng chuỗi ở kịch bản ấy là **trần 8 lượt**, không phải nhánh ẩn danh.

Ca mới `stops retrying once the session is known to be anonymous` chứng minh nhánh ẩn danh chạy đúng — nhưng nó tới được `anonymous` bằng một **401** trước, tức một kịch bản khác với kịch bản chú thích mô tả. Hai guard đều đúng; chỉ có phần gán công là sai, và đó là loại chú thích đưa người gỡ lỗi sau tới nhầm nhánh.

### [D] Quan sát — có từ trước, KHÔNG phải finding của lượt 2

`resolveExpiresAt` dựng `expiresAt = now + expiresIn * 1000` từ đồng hồ **cục bộ** khi thân trả `expiresIn`, nhưng `scheduleRefreshFromSession` tính `remainingMs = expiresAt - (now + serverOffsetMs)` — trừ lệch đồng hồ khỏi một mốc vốn đã ở hệ quy chiếu cục bộ. Với đồng hồ nhanh chín phút, quãng đời token bị ước lượng **sai lệch nguyên cả phần lệch**. Hợp đồng W16 luôn gửi `expiresAt` (B1-01 #3, `tools/contract/strict/refresh.ts`), nên nhánh `expiresIn` là đường tương thích mà BE không bao giờ đi. Ghi lại vì [4] sửa đúng chỗ tính `remainingMs`; không tính vào lượt này.

---

## Hai điều người điều phối hỏi riêng

### 1. `src/api/__tests__/urlJoiners.test.ts` — file mới ngoài khối [10]

**Xứng đáng tồn tại, và đang ở ĐÚNG thư mục. Ghi là "lệch khỏi prompt có lý do đứng vững", không phải nợ.**

Ba lý do, lý do đầu là lý do quyết định:

1. **Đây là chỗ duy nhất đặt được mà không phạm mục 0.4.** File phải nhập cả `toApiUrl` (`src/api`) lẫn `resolveAuthUrl` (`src/lib/auth`). Đặt dưới `src/api/__tests__/` thì chiều nhập là api → lib, tức chiều xuôi, hợp lệ. Đặt dưới `src/lib/auth/__tests__/` thì chiều nhập là **lib → api** — đúng cạnh mà ranh giới 0.4 tồn tại để chặn, và cũng đúng lý do hai hàm phải tách đôi ngay từ đầu. `pnpm lint` và `pnpm cycles` đều 0 ở lượt này, xác nhận chiều đã chọn là chiều hợp lệ.
2. **Gộp vào file có sẵn là chôn nó đi.** `src/api/__tests__/notifications.test.ts` đã có đụng `toApiUrl`, nhưng file ấy nói về các đường của thông báo; một bất biến "hai hàm ở hai tầng phải bằng nhau" giấu bên trong nó thì không ai tìm ra. Giá trị của bảng này nằm ở chỗ **tìm được** — và hai docblock chéo nhau nay trỏ thẳng vào file theo tên, điều chỉ có nghĩa khi file được đặt tên theo đúng bất biến nó giữ.
3. **Chi phí gần như bằng không**: 61 dòng, một bảng, không một dòng mã sản phẩm.

### 2. Đổi 5 → 9 — chấp nhận được hay phải quay lại?

**Chấp nhận được. Không phải quay lại con số cũ.** Bốn lý do, ba trong số đó đo được:

1. **Không thể vừa giữ 5 vừa sửa LOG-02.** Với TTL 30 s, "5 lượt trong 120 giây" kéo theo nhịp 30 giây, kéo theo mỗi lượt gia hạn rơi **đúng lúc** token chết. Con số 5 *chính là* lỗi LOG-02, viết dưới dạng một quan sát. Giữ 5 là giữ lỗi. Lập luận của tác giả đứng vững ở điểm này.
2. **Ở sản phẩm, thay đổi này là một no-op ĐO ĐƯỢC.** `ACCESS_TOKEN_TTL_S = 600` (B1-01, `ge=1, le=600`). Kẹp nửa quãng đời chỉ có hiệu lực khi `remainingMs < 60 000` — xem bảng ở [A]: mọi TTL từ 60 s trở lên cho ra **cùng một con số** trước và sau. Ở TTL thật của BE, lịch hẹn trước và sau giống nhau từng mili-giây. Con số 5 → 9 chỉ nhìn thấy được trong một bộ mẫu 30 giây.
3. **Không chạm trần nào của BE.** `REFRESH_TOTAL_LIMIT` 300/60 s và `REFRESH_FAIL_LIMIT` 20/60 s theo `sid` (B1-01). Trường hợp bộ mẫu xấu nhất là 4 lượt/phút. Và `REFRESH_GRACE_S = 30`: hai lượt gia hạn nằm trong cùng một cửa sổ ân hạn đúng là thứ ân hạn được đặc tả để hấp thụ (*"nhiều thẻ refresh cùng cookie trong 30 s nhận cùng kết quả"*, `be-cho-fe.md:19`), nên nhịp nhanh hơn cũng không sinh rủi ro thu hồi do dùng lại cookie.
4. **Ca mới KHOÁ được tính chất, không phải nới lỏng khẳng định.** Nó thay một khoảng mở (`>1` và `<=5`) bằng `toHaveLength(9)` chính xác **cộng thêm** hai khẳng định tính chất: `gaps.every((gap) => gap < TOKEN_TTL_MS)` — không lượt nào tới sau khi token trước đã chết — và `Math.max(...gaps) === TOKEN_TTL_MS / 2`. Khẳng định thứ hai chặt **hai chiều**, trong khi khẳng định cũ chỉ chặn một chiều và chặn sai chiều. Đây là siết, không phải nới.

**"Nửa quãng đời còn lại" có phải một hằng thời lượng trá hình không? — KHÔNG.**

- `Math.floor(remainingMs / 2)` có hằng số duy nhất là `2`, một **số chia** áp lên một giá trị lúc chạy. Nó không sinh ra một con số mili-giây cố định nào; độ trễ kết quả co giãn theo đúng TTL mà máy chủ cấp. Một tỉ lệ không phải một thời lượng.
- Mục B của `CLAUDE.md` nói về **chuyển động** — `MOTION_DURATIONS_MS` ở `src/lib/motion/tokens.ts`, nhịp mà một phần tử *chuyển* từ trạng thái này sang trạng thái kia. Bằng chứng phạm vi: `refresh.ts` từ trước đã mang `REFRESH_LEAD_TIME_MS` 60 000, `REFRESH_MIN_INTERVAL_MS` 30 000, `REFRESH_TIMEOUT_MS` 15 000, `bootstrap.ts` mang 1 000 và 60 000 — và `pnpm lint --max-warnings 0` sạch ở cả hai lượt. Thời lượng của tầng mạng chưa bao giờ nằm trong phạm vi luật ấy; một tỉ lệ lại càng xa hơn.

Nói thêm cho đề xuất sửa [A]: dùng `RETRY_MIN_DELAY_MS` có sẵn thay vì viết một hằng mới, nên lời sửa ấy cũng không sinh hằng thời lượng nào.

---

## Điểm

| Miền | Trọng số | Lượt 1 | Lượt 2 | Tích |
|---|---|---|---|---|
| SEC | 0,15 | 5,0 | 5,0 | 0,75 |
| CON | 0,20 | 3,0 | **5,0** | 1,00 |
| RES | 0,15 | 3,0 | **3,5** | 0,525 |
| LOG | 0,15 | 4,0 | **5,0** | 0,75 |
| API / hợp đồng | 0,10 | 5,0 | 5,0 | 0,50 |
| TEST | 0,15 | 4,0 | **4,5** | 0,675 |
| OBS / MNT | 0,10 | 5,0 | 4,5 | 0,45 |

**Tổng: 4,65 / 5** (lượt 1: 4,00)

RES là miền duy nhất gần như đứng yên: [2] được sửa tốt, nhưng [4] mở ra [A] ở ngay miền ấy.

---

## PHÁN QUYẾT: REQUEST CHANGES

Vòng sửa này tốt. P1 của lượt 1 được sửa đúng bằng lời sửa nhỏ nhất, và ca test kèm theo đánh trúng cái khe mà bộ test cũ bỏ trống — đếm kết nối còn sống thay vì đếm số lần dựng. Hai P2 và ba P3 đều đã đóng, [5] còn đi xa hơn đề xuất của tôi (gộp hành vi thay vì ghi nợ, `endpoints.ts` lên 100/100), Nit [8] biến một lần đối chiếu tay thành một bất biến tự giữ. Cổng bảy bước xanh với mã thoát thật, độ phủ **tăng** dù vừa thêm ba nhánh mới, e2e không đỏ thêm bài nào. Điểm từ 4,00 lên 4,65.

Chặn vì đúng **một** finding mới, và nó nằm ở chính chỗ đề bài bảo tôi soi kỹ nhất. Hướng của [4] đúng — sàn phải co theo quãng đời token, không phải thắng nó — nhưng `Math.min(floorMs, latestSafeMs)` để sàn co về **0** khi `remainingMs` co về 0, và một lượt gia hạn **thành công** trả token đã chết sẽ hẹn lượt kế ở độ trễ 0 rồi lặp mãi. Trần 8 lượt của [2] không cứu được vì nó canh đường lỗi, còn đây là đường thành công. Đo A/B trên cùng một bộ mẫu: mã hiện tại **18** lượt gia hạn trong 1 giây giả, công thức cũ **0**. Và khối chú thích mới đang khẳng định đúng điều ngược lại, nên người đọc sau sẽ tin vòng lặp ấy không thể xảy ra.

Đường tới được là hẹp — cần BE trả token đã chết, hoặc thiếu tiêu đề `Date` cộng đồng hồ nhanh hơn TTL, hoặc `ACCESS_TOKEN_TTL_S` đặt rất thấp. Ở TTL mặc định 600 s, thay đổi của [4] là một no-op đo được. Tôi vẫn chặn vì hình dạng hỏng là loại xấu nhất (vòng quay không trần, mỗi thẻ một vòng, đập vào một máy chủ vốn đã trục trặc), vì đây là **hồi quy do chính vòng sửa này sinh ra**, và vì lời sửa là một dòng dùng lại một hằng số đã có.

**Phải sửa trước khi gộp vào `master`:**

1. **[A] P2** — `const delayMs = Math.max(idealMs, Math.min(floorMs, latestSafeMs), RETRY_MIN_DELAY_MS);` (`refresh.ts:220`), sửa câu *"vẫn chặn được vòng lặp gia hạn liên tục"* trong khối chú thích cho khớp, và thêm một ca: một lượt gia hạn **thành công** trả token đã hết hạn không được sinh quá một nhúm lượt trong một giây.

**Nên sửa kèm (hai món, cùng file, cùng vùng mã, đều là câu chữ hoặc một dòng):**

2. **[B] P3** — đặt `transientAttempt = 0` ở đường khởi động lại, hoặc đổi tên ca `restarts the ladder…` và sửa docblock cho khớp điều thật sự xảy ra.
3. **[C] Nit** — chú thích `handleTransientFailure` đang gán công cho nhánh ẩn danh ở một kịch bản mà trạng thái là `unknown`.

Hai phán riêng: file `urlJoiners.test.ts` **được chấp nhận ở đúng chỗ nó đang nằm** (ghi vào "Lệch khỏi prompt", không phải nợ); đổi 5 → 9 **được chấp nhận**, không quay lại con số cũ. Quan sát [D] có từ trước, ngoài phạm vi lượt này. Hai bài e2e đỏ vẫn là nợ đã ghi của một prompt riêng.
