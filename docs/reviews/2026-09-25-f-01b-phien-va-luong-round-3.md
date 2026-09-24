# Review merge lượt 3 — `feature/f-01b-phien-va-luong` → `master` (AppFront)

- Ngày: 2026-09-25 · Reviewer: phiên `/merge-review` (worker Orca `task_2edd078da768`)
- Lượt 1: `2026-09-24-f-01b-phien-va-luong.md`, commit `6691e00` — `REQUEST CHANGES`, 1 P1 + 2 P2 + 3 P3 + 3 Nit
- Lượt 2: `2026-09-24-f-01b-phien-va-luong-round-2.md`, commit `6cc6080` — `REQUEST CHANGES`, 1 P2 mới (RES-04) + 1 P3 + 1 Nit
- Sha mới: `43fd7d4` · trước sửa `dd27f78` · nền vẫn `master` `0774abfd6e11`
- Phạm vi lượt này: **chỉ** `git diff dd27f78..43fd7d4` — 3 file, 1 commit, +117 / −15
- Cây làm việc: sạch

---

## Cổng — chạy độc lập

`pnpm verify` (log `…/scratchpad/verify-r3.log`, dòng cuối `EXIT=0`)

| Bước | Kết quả |
|---|---|
| typecheck · lint · import vòng · test+độ phủ · build · kích thước gói · độ dài file | **cả bảy đạt** |

- **335/335 file · 7075/7075 ca.** Khớp chính xác con số tác giả khai.
- Kích thước gói: 162,4/175 · 162,4/170 · 257,4/280 · CSS 10,9/12 · tổng JS 1062,9/800 (cảnh báo cũ). Khớp.
- `pnpm e2e`: **13 đạt / 2 đỏ**, và hai bài đỏ đúng là hai bài nợ có tên cũ — `viewer3d.spec.ts:479` (P2) và `:521` (Q2). Không bài nào đỏ thêm. Khớp.

### Độ phủ — cao hơn tác giả khai, và tăng đều qua ba lượt

| | lượt 1 | lượt 2 | **lượt 3** |
|---|---|---|---|
| `src/lib/auth` | 92,66 / 85,88 | 92,74 / 86,05 | **92,78 / 86,16** |
| `refresh.ts` | 94,93 / 81,63 | 95,08 / 82,17 | **95,14 / 82,52** |
| `bootstrap.ts` | 100 / 100 | 100 / 100 | **100 / 100** |

Tác giả khai `src/lib/auth` 89,65 / 82,77 và tự giải thích là con số của một lượt chạy **targeted** chỉ `src/lib/auth`. Đúng như thế: ở lượt chạy đầy đủ, con số là 92,78 / 86,16. Tác giả khai **thấp hơn** thực tế, không cao hơn.

Chuyện lượt verify đầu của tác giả dừng ở bước lint vì `import/no-duplicates` (nhập `../bootstrap` hai dòng) cũng khớp với mã: `refresh.test.ts:3` nay là **một** dòng `import { RETRY_MIN_DELAY_MS, __resetLastKnownUserForTests } from '../bootstrap';`. Bước lint của tôi đạt.

---

## Ba finding của lượt 2 — trạng thái

| # | Lượt 2 | Trạng thái |
|---|---|---|
| [A] | **P2** RES-04 (chặn gộp) | ✅ **ĐÃ SỬA ĐÚNG**, kiểm chứng bằng A/B |
| [B] | P3 RES-05 | ✅ **ĐÃ SỬA**, chọn hướng khó hơn và đúng hơn |
| [C] | Nit MNT-09 | ✅ đã sửa |
| [D] | quan sát, có từ trước | ✅ không sửa, **ghi nợ có tên trong thân commit** — đúng như đề bài yêu cầu |

### [A] RES-04 — đúng một dòng, và tôi đã tự kiểm chứng ca test bắt được lỗi

```ts
const delayMs = Math.max(idealMs, Math.min(floorMs, latestSafeMs), RETRY_MIN_DELAY_MS);
```

Đúng lời sửa tôi đề nghị, dùng lại hằng có sẵn ở `bootstrap.ts:109` nên không sinh hằng thời lượng mới. Đối chiếu bảng hành vi:

| `remainingMs` | lượt 2 | **lượt 3** |
|---|---|---|
| 600 000 (TTL thật của BE) | 540 000 | 540 000 — **không đổi** |
| 60 000 | 30 000 | 30 000 — **không đổi** |
| 30 000 | 15 000 | 15 000 — **không đổi** (chỗ [4] sửa vẫn nguyên) |
| 1 000 | 500 | **1 000** |
| 0 | **0** ← vòng quay | **1 000** |
| −510 000 | **0** ← vòng quay | **1 000** |

**A/B tôi tự chạy** — gỡ `RETRY_MIN_DELAY_MS` khỏi `Math.max` rồi chạy lại `refresh.test.ts`:

```
× does not spin when a successful refresh hands back an already-dead token
  → expected [...] to have a length of 2 but got 19
```

**19** — khớp chính xác con số tác giả khai, và khớp con số 18 tôi đo ở lượt 2 cộng lượt dựng phiên. Ca mới thật sự bắt được lỗi, không phải một ca trang trí.

Và ca ấy khoá **nhịp chính xác**, không chỉ khoá "không quay tít": sau 1 giây giả đúng 2 lượt, sau 10 giây giả đúng `1 + 10_000 / RETRY_MIN_DELAY_MS` = 11 lượt. Một sàn dưới bị đặt sai giá trị cũng làm nó đỏ.

Khối chú thích khẳng định ngược sự thật ở lượt 2 — *"vẫn chặn được vòng lặp gia hạn liên tục"* — đã viết lại, và bản mới nói đúng **vì sao** tỉ lệ nửa-quãng-đời tự nó không chặn được (`latestSafeMs` co về 0 theo `remainingMs`, `Math.min` kéo sàn xuống theo) và **vì sao** trần `REFRESH_MAX_TRANSIENT_ATTEMPTS` không cứu được (nó canh đường lỗi, đây là đường thành công). Chú thích nay mô tả đúng mã.

**Một chỗ chưa chính xác trong chú thích, không phải finding:** câu *"chỉ `remainingMs ≲ 0` mới chạm tới nó"*. Sàn dưới thật sự bắt đầu có hiệu lực từ `remainingMs < 2 000` ms (vì `latestSafeMs = ⌊remaining/2⌋ < 1 000` ⟺ `remaining < 2 000`). Dấu `≲` đã hedge sẵn, và hai giây không đổi kết luận nào — ghi lại cho chính xác thôi.

**Nhịp còn lại sau khi vá, nói thẳng:** ở kịch bản token chết lặp lại, vòng lặp bị chặn ở **1 lượt/giây** chứ không phải biến mất. Đó là 60 lượt/phút — dưới `REFRESH_TOTAL_LIMIT` 300/60 s của BE, và tự lành ngay khi máy chủ trả về một token còn sống. Cao hơn nhịp 2 lượt/phút của mã trước lượt 2, nhưng "có trần" mới là yêu cầu, và `RETRY_MIN_DELAY_MS` chính là hằng tôi đề nghị. Không mở lại.

### [B] RES-05 — chọn hướng reset thật, và ca test nay khoá được

Lượt 2 tôi để hai lựa chọn: đặt `transientAttempt = 0` ở đường khởi động lại (làm chú thích thành đúng), hoặc đổi tên ca cho khớp điều thật sự xảy ra. Tác giả chọn cái đầu — hướng khó hơn và đúng hơn, vì một người quay lại thẻ sau bữa trưa xứng đáng có một thang mới chứ không phải một lượt lẻ.

Reset đặt ở hai chỗ, và tôi đã soát cả hai:

1. **Trong `scheduleRefreshFromSession`**, ngay trước `setTimeout`, tức **sau** ba lượt thoát sớm (`status !== 'authenticated'`, `expiresAt === null`, `isDocumentHidden()`). Nên nó chỉ chạy khi thật sự có một lượt chủ động được hẹn — đúng như chú thích nói.
2. **Trong `refreshSingleFlight` khi `reason === 'bootstrap'`**, tức nút "thử lại" của `SessionGate` (`retryAppSession()` → `bootstrapSession()`), và đặt **sau** cổng `refreshFailed` nên một lượt bị cổng chặn không reset gì.

**Có mở lại RES-03 (thang lùi không trần) không? — Không.** `scheduleRefreshFromSession()` có đúng **hai** nơi gọi trong cả file: `onVisibilityChange` khi thẻ hiện lại (`refresh.ts:264`) và ngay sau `setAuthenticatedSession` của một lượt gia hạn **thành công** (`:469`). Cả hai đều là điểm reset hợp lệ — một cái là hành động của người dùng/trình duyệt, cái kia là bằng chứng máy chủ còn sống. **Không** đường hẹn-giờ nào gọi nó, nên trong một sự cố kéo dài thang lùi vẫn chạy đúng 8 lượt rồi đứng im. Trần của RES-03 còn nguyên.

Trường hợp người dùng lật thẻ liên tục trong lúc máy chủ hỏng: mỗi lần lật là một lượt được hẹn, nhưng token lúc ấy vẫn khoẻ (lỗi tạm không làm token chết) nên `idealMs` thắng và lượt ấy được hẹn xa. Không thành đường đập.

**A/B tôi tự chạy** — gỡ `transientAttempt = 0` khỏi `scheduleRefreshFromSession`:

```
× restarts the ladder when the tab comes back into view
  → expected 10 to be 17
```

`10 = 1 + 8 + 1` — đúng hình dạng "một lượt lẻ" tôi mô tả ở lượt 2; `17 = 1 + 8 + 8` là một thang mới đầy đủ. Ca này nay khoá được đúng thứ nó mang tên. Khẳng định siết từ `toBeGreaterThan(afterGivingUp)` — mà một lượt lẻ cũng đủ xanh — thành hai con số chính xác `1 + REFRESH_MAX_TRANSIENT_ATTEMPTS` rồi `1 + REFRESH_MAX_TRANSIENT_ATTEMPTS * 2`. Tên ca giữ nguyên vì nay nó đúng.

### [C] MNT-09 — chú thích trả công đúng nhánh

Bản mới nói rõ hai guard canh **hai kịch bản khác nhau**: nhánh `anonymous` chỉ tới được sau một lượt **401**, còn kịch bản khách chưa đăng nhập đứng ở `/login` lúc máy chủ chết thì trạng thái là **`unknown`** (một cú 502 là lỗi tạm, nó không đặt phiên về ẩn danh) và thứ dừng chuỗi ở đó là **trần 8 lượt**. Đúng.

### [D] — không sửa, ghi nợ có tên

Thân commit ghi đủ: `resolveExpiresAt` dựng `expiresAt = now + expiresIn * 1000` từ đồng hồ **cục bộ**, trong khi `scheduleRefreshFromSession` tính `remainingMs = expiresAt - (now + serverOffsetMs)` — trừ lệch đồng hồ khỏi một mốc vốn đã ở hệ quy chiếu cục bộ; chỉ nhánh thân trả `expiresIn` tới được, và hợp đồng W16 luôn gửi `expiresAt` nên BE không bao giờ đi nhánh ấy. Đúng nội dung tôi nêu, đúng đánh giá phạm vi, và ghi ở chỗ tìm lại được. Đạt yêu cầu "ghi nợ có tên".

---

## Câu hỏi riêng: ca `pauses proactive refresh while hidden and resumes on visibilitychange` bị nới hay không?

**Không bị nới. Hai khẳng định giữ nguyên từng ký tự; chỉ cửa sổ quan sát dời đi.**

Toàn bộ thay đổi trong `session.test.ts` là một dòng: `await flush()` → `await vi.advanceTimersByTimeAsync(RETRY_MIN_DELAY_MS)`. Cả hai khẳng định đếm chính xác đứng nguyên:

```ts
await vi.advanceTimersByTimeAsync(120_000);
expect(refreshCalls).toBe(1);          // ẩn thì DỪNG — không đổi
…
await vi.advanceTimersByTimeAsync(RETRY_MIN_DELAY_MS);
expect(refreshCalls).toBe(2);          // hiện lại thì NỐI LẠI — không đổi
```

Không khẳng định nào bị đổi thành khoảng, thành `toBeGreaterThan`, hay bị xoá. Bài vẫn đỏ nếu ẩn thẻ mà lượt gia hạn vẫn chạy, và vẫn đỏ nếu hiện lại mà nó không nối lại. Nghĩa của bài không đổi.

**Giải thích của tác giả về nguyên nhân cũng đúng.** Bài ấy dùng `expiresIn: 120` rồi ẩn thẻ đúng 120 giây, nên lúc hiện lại `remainingMs` bằng 0. Trước lượt này, độ trễ dựng từ một `remainingMs` thoái hoá như thế là **0**, nên `flush()` (advance 0 ms) đủ để thấy lượt thứ hai — tức bài xanh **nhờ** chính lỗi RES-04. Nay độ trễ là `RETRY_MIN_DELAY_MS`, nên cửa sổ quan sát phải rộng bằng đúng nhịp mới. Đó là sửa bài cho khớp một hành vi đã sửa đúng, không phải nới cho xanh.

**Một chỗ tôi phải tự đính chính.** Trước khi chạy A/B tôi đã nghĩ bài này, sau khi sửa, còn **chặt hơn** bản cũ vì cửa sổ 1 000 ms sẽ nhìn thấy vòng quay nếu RES-04 quay lại. Đo ra thì không phải: trong lượt A/B gỡ `RETRY_MIN_DELAY_MS`, `refresh.test.ts` đỏ còn **`session.test.ts` vẫn xanh**. Lý do là máy chủ giả của bài ấy trả một token **khoẻ** (`expiresIn: 120`) ở mỗi lượt, nên chỉ token *đầu* đã chết; lượt gia hạn thứ hai cho `remainingMs = 120 000` và lịch hẹn kế đi theo `idealMs`, không có vòng nào để quay. Bài này **trung tính** với RES-04 — không mạnh hơn, không yếu hơn. Thứ canh RES-04 là ca mới `does not spin…`, và ca ấy canh được (19 so với 2).

Tóm lại: bài giữ đúng phạm vi nó vẫn có, và phạm vi ấy không bao gồm RES-04 — cả trước lẫn sau. Không có gì bị nới.

---

## Điểm

| Miền | Trọng số | lượt 1 | lượt 2 | **lượt 3** | Tích |
|---|---|---|---|---|---|
| SEC | 0,15 | 5,0 | 5,0 | 5,0 | 0,75 |
| CON | 0,20 | 3,0 | 5,0 | 5,0 | 1,00 |
| RES | 0,15 | 3,0 | 3,5 | **5,0** | 0,75 |
| LOG | 0,15 | 4,0 | 5,0 | 5,0 | 0,75 |
| API / hợp đồng | 0,10 | 5,0 | 5,0 | 5,0 | 0,50 |
| TEST | 0,15 | 4,0 | 4,5 | **5,0** | 0,75 |
| OBS / MNT | 0,10 | 5,0 | 4,5 | **5,0** | 0,50 |

**Tổng: 5,00 / 5** (lượt 1: 4,00 · lượt 2: 4,65)

RES về 5,0 vì đây là lượt đầu tiên cả ba lớp của nó cùng đứng: trần cho đường lỗi, sàn dưới cho đường thành công, và một đường khởi động lại tử tế. TEST về 5,0 vì hai ca then chốt của lượt này đều được **tôi** kiểm chứng là bắt được lỗi, không phải chỉ được khai là thế.

---

## PHÁN QUYẾT: APPROVE

Vòng sửa này đóng nốt finding duy nhất còn lại và đóng đúng cách. [A] là đúng một dòng tôi đề nghị, dùng lại `RETRY_MIN_DELAY_MS` có sẵn nên không sinh hằng thời lượng mới, và ba cột hành vi quan trọng — TTL 600 s của BE, TTL 30 s, và `remainingMs ≲ 0` — lần lượt là không đổi, không đổi, và hết quay. [B] chọn hướng khó hơn (reset thật thay vì đổi tên ca) nên mã, chú thích và tên ca nay cùng nói một điều, mà không mở lại trần của RES-03: `scheduleRefreshFromSession` có đúng hai nơi gọi và cả hai là điểm reset hợp lệ. [C] trả công đúng nhánh, [D] ghi nợ có tên trong thân commit.

Tôi không nhận con số của tác giả mà tự chạy lại A/B cho cả hai ca then chốt, đúng cách đã làm với P1 ở lượt 2: gỡ sàn dưới ra thì `does not spin…` đỏ với **19 lượt thay vì 2** (khớp con số 18 tôi đo ở lượt 2 cộng lượt dựng phiên); gỡ reset ra thì `restarts the ladder…` đỏ với **10 thay vì 17** — đúng hình dạng "một lượt lẻ" tôi mô tả. Cổng bảy bước xanh với mã thoát thật, 7075/7075 ca, độ phủ **cao hơn** con số tác giả khai và tăng đều qua cả ba lượt, e2e 13/15 đúng hai bài nợ có tên cũ.

Ca `pauses proactive refresh while hidden…` **không bị nới**: hai khẳng định đếm chính xác giữ nguyên từng ký tự, chỉ cửa sổ quan sát dời từ 0 ms sang 1 000 ms để khớp một nhịp đã được sửa đúng. Tôi tự đính chính một suy đoán của chính mình ở đây — bài ấy trung tính với RES-04 chứ không chặt hơn, vì máy chủ giả của nó trả token khoẻ ở mỗi lượt; đo ra mới thấy.

**Nhánh `feature/f-01b-phien-va-luong` (`43fd7d4`) GỘP ĐƯỢC vào `master`, với hai nợ có tên đã ghi:**

1. **`e2e/viewer3d.spec.ts` chưa được thẩm định lại dưới bộ mẫu.** Mục 4.10 bật `VITE_USE_MOCK_API=true` cho máy chủ e2e, nên mỗi lượt chạy là "người dùng lần đầu có bạn cộng tác giả" và ít nhất ba lớp phủ xuất hiện ở ba thời điểm. Hai bài đỏ — `viewer3d.spec.ts:479` (P2) và `:521` (Q2) — đỏ vì đúng việc đó, không bài nào đỏ vì ảnh chuẩn. Tôi đã chạy lại e2e ở cả ba lượt và con số giữ nguyên 13/15 với đúng hai bài ấy. Thuộc một prompt riêng.
2. **`resolveExpiresAt` ([D]).** Dựng `expiresAt` từ đồng hồ **cục bộ** khi thân trả `expiresIn`, trong khi `remainingMs` lại trừ `serverOffsetMs` — với đồng hồ lệch thì quãng đời token bị ước lượng sai nguyên phần lệch. Chỉ nhánh `expiresIn` tới được; hợp đồng W16 luôn gửi `expiresAt` nên BE không bao giờ đi nhánh ấy, nó chỉ là đường tương thích. Có từ trước F-01b. Đã ghi nợ có tên trong thân commit `43fd7d4`.

Không còn finding nào ở mức P0, P1, P2 hay P3. Việc gộp thuộc phiên gọi tôi — tôi không tự gộp.
