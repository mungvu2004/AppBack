# Review merge lượt 2 — `feature/f-02-go-mock-va-luu-gia` → `master` (AppFront)

- Ngày: 2026-09-25 · Reviewer: phiên `/merge-review` (worker Orca, worktree riêng `f-02-review-r2`)
- Repo: `F:/AppFront` · Commit đầu nhánh: `b2fccb10cff9` · Trước vòng sửa: `338242a03b39` · Nền: `master` `b06acc5956b6`
- Phạm vi lượt này: **chỉ** `git diff 338242a..b2fccb1` — 11 file, +117 / −27, một commit. Toàn nhánh đã soát ở lượt 1.
- Lượt 1: `docs/reviews/2026-09-25-f-02-go-mock-va-luu-gia.md` — **APPROVE**, 4,58/5, 0 P0, 0 P1, 1 P2 + 4 P3 + 3 Nit.
- Đề bài vòng sửa: `backend/dieu-phoi/chay/F-02/spec-fix.md` (sáu món + một món ghi nợ).
- Cổng: xem mục 2 — **cả bảy bước đã quan sát đạt**, nhưng không trong cùng một lượt `pnpm verify`. `pnpm coverage` sạch: 340/340 file · 7136/7136 test · mã thoát 0.

---

## 1. Điều kiện dừng sớm — không cái nào chạm

| Điều kiện | Kết quả |
|---|---|
| Cây làm việc bẩn | `git status --porcelain` **rỗng** |
| Dòng đầu commit sai mẫu / thiếu trailer | `fix(measurements): rethrow the original error, gate delete-gone on 404` ✓ Conventional · trailer `Prompt: F-02` ✓ |
| Chạm file cấm (khối **[12]** của prompt) | `git diff` trên `src/api/**`, `src/routes/**`, `src/store/**`, `src/lib/{http,auth,autosave,query}/**`, `vitest.config.ts`, `eslint-rules/**`, `package.json`, `scripts/**` — **rỗng**. Một chỗ sát ranh giới: xem finding #5 |
| Dấu hiệu lách cổng | `git diff … \| grep -Ei 'ts-ignore\|ts-expect-error\|as unknown as\|eslint-disable\|it\.skip\|it\.todo\|\.only'` trên các dòng `+` — **0 dòng**. Không hạ ngưỡng nào |
| Sổ nợ | Thân commit `b2fccb1` có **một** dòng nợ MNT-04, dẫn `useViewer3DSource.ts:7-9`, `useViewerShell.ts:90`, `check-bundle-size.mjs:472-474`. Tôi mở cả ba: **đúng chỗ** — hai chỗ đầu vẫn là `import` tĩnh, chỗ thứ ba là đúng lời khuyên "lazy-load / đưa fixture ra khỏi gói". AppFront không có `DEBT.md`; thân commit là chỗ ghi nợ của repo này |

---

## 2. Bằng chứng cổng — tự chạy, không lấy số tác giả

### 2.1 Bảy bước: **đã quan sát cả bảy đạt**, nhưng KHÔNG trong cùng một lượt `pnpm verify`

| Bước | Lượt verify #1 | Lượt verify #2 | Chạy riêng |
|---|---|---|---|
| 1 typecheck | **đạt** | **đạt** | — |
| 2 lint (`--max-warnings 0`) | **đạt** | **đạt** | — |
| 3 import vòng | **đạt** | **đạt** | — |
| 4 test + độ phủ | **HỎNG** 2/7136 | **HỎNG** 3/7136 | **đạt** — `pnpm coverage` sạch: **340/340 file · 7136/7136 test · mã thoát 0**, ngưỡng độ phủ theo tầng đạt |
| 5 build | chưa chạy | chưa chạy | **đạt** (`pnpm build`, mã thoát 0) |
| 6 kích thước gói | chưa chạy | chưa chạy | **đạt** (`pnpm size`, mã thoát 0) |
| 7 độ dài file | chưa chạy | chưa chạy | **đạt** (`pnpm length`, mã thoát 0) |

Hai lượt `pnpm verify` đều dừng ở bước 4, nên tôi **không ký "7/7 đạt"** (E.10). Nhưng tôi đã tự chạy từng bước còn lại và **thấy tận mắt cả bảy đều đạt**, kể cả bước 4:

```
pnpm coverage        →  Test Files 340 passed (340) · Tests 7136 passed (7136) · EXIT=0
pnpm build && pnpm size && pnpm length   →  EXIT=0
```

Con số `7136/7136` của tác giả **khớp**.

- `pnpm size` — **màn hình đầu 163,0 KiB** / 175 · **chunk lớn nhất 163,0** / 170 · chi phí thêm một màn 264,2 / 280 · **CSS 10,9** / 12 → bốn ngân sách **chặn cổng** đều đạt. `tổng JS 1065,2 / 800` ghi **QUÁ MỐC** nhưng không chặn (mã thoát 0) — đúng như lượt 1 ghi, và khớp từng con số tác giả khai (163,0 · 163,0 · 10,9 · 1065,2).
- `pnpm length` — chỉ có mức "nhắc", cao nhất 398 dòng (`CommentThread.tsx`); **không** file nào chạm trần 400.

### 2.2 Độ phủ — đo lại, khớp

Từ chính lượt `pnpm coverage` mã thoát 0 ở trên:

| File | % dòng | % nhánh | Tác giả khai |
|---|---|---|---|
| `src/domain/measure/measure.ts` | **94,14** | 91,22 | 94,14 ✓ |
| `src/lib/mutations/measurement.ts` | **100** | **90,9** | 100 / 90,9 ✓ |
| Toàn bộ | 84,13 | 86,27 | — |

Mã thoát 0 nghĩa là ngưỡng theo tầng ở `vitest.config.ts:54-67` (`src/domain` 90 %, `src/lib` 80 %) **đạt**. Không có ngưỡng nào bị hạ: `git diff` trên `vitest.config.ts` rỗng.

### 2.3 Bước 4 đỏ hai lượt — đã truy, là **flake hết giờ**, không phải lỗi mã

| Lượt | Lệnh | Kết quả |
|---|---|---|
| verify #1 | `pnpm verify` | đỏ 2 ca: `Viewer3DPanels.test.tsx` `[VP-1]` · `Viewer3DOverlays.test.tsx` |
| verify #2 | `pnpm verify` | đỏ 3 ca: `[VP-1]` · `MobileViewer.container.test.tsx` · `VersionHistory.test.tsx` |
| #3 | `pnpm coverage -- --retry=2` | đỏ 1 ca: `[VP-1]` |
| #4 | `pnpm coverage` | **xanh 340/340 · 7136/7136 · mã thoát 0** |

Bằng chứng nói đây là flake, không phải lỗi:

1. **Tập ca đỏ đổi mỗi lượt** trên cùng một sha, cùng một máy; và lượt thứ tư xanh sạch. Lỗi thật không cư xử như thế.
2. **Mọi ca đỏ đều là hết giờ** — `waitFor` quá trần 4000 ms hoặc `Test timed out in 5000ms`. Không một `AssertionError` nào.
3. **Chạy riêng thì xanh**: `Viewer3DPanels + Viewer3DOverlays` → 17/17 trong 4,81 s; `Viewer3DPanels + MobileViewer.container + VersionHistory` → 3/3 file xanh.
4. **Nhánh không chạm đường đó.** `git diff --name-only b06acc5..b2fccb1` (cả nhánh) không có `Viewer3DPanels*`, `Viewer3DOverlays*`, `PropertyInspector/**`, `VersionHistory*`, `MobileViewer.container*`, `lib/testing/render.tsx`. Ca `[VP-1]` chờ đúng một `lazy(() => import('@/screens/viewer/PropertyInspector'))` (`Viewer3DPanels.tsx:63-64`) — module graph mà nhánh này không đụng.
5. **Nền cũng xanh**, đo tại chỗ: `master` `b06acc5` → `pnpm test` 335/335; `338242a` (trước vòng sửa) → `pnpm test` 340/340, **hai lượt**.

**Một điều tôi đã đo nhưng KHÔNG kết luận được.** Tỉ lệ đỏ ở `b2fccb1` (3 đỏ / 4 lượt) cao hơn hẳn ở `338242a` (0 đỏ / 2 lượt) và `master` (0 / 1). Nhưng hai nhóm **không cùng điều kiện**: bốn lượt ở `b2fccb1` chạy **có** độ phủ (`verify` bước 4 và `pnpm coverage`), còn hai lượt đối chứng chạy `pnpm test` **không** độ phủ — mà đo đạc độ phủ làm mọi thứ chậm đi. Tôi **không** chạy đối chứng có độ phủ ở `338242a`, nên **không** có cơ sở nói vòng sửa làm cổng lung lay hơn. Số duy nhất đáng ghi: `useMeasurementTool.test.tsx` đi từ **2953 / 3029 ms** (`338242a`) lên **5282 ms** (`b2fccb1`, lượt có độ phủ) — hai ca cổng-thật mới có giá của nó, và một phần giá đó là lượt ngủ 50 ms ở finding #1.

## 3. Sáu món — từng món một

| # | Món | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | P2 TEST-03/LOG-06 — ném lại **lỗi gốc** | **đã sửa đúng, đủ hai đường** | xem 3.1 |
| 2 | P3 LOG-07 — "đã bị xoá ở nơi khác" phải kiểm 404 | **đã sửa đúng** | xem 3.2 |
| 3 | P3 TEST-05 — bài kiểm bản nháp phải đếm điểm | **đã sửa đúng** | xem 3.3 |
| 4 | P3 MNT-02 — tách bốn dòng nối | **đã sửa đúng** (một lưu ý ranh giới, finding #5) | xem 3.4 |
| 5 | Nit MNT-06 — đừng ném chuỗi kỹ thuật | **đã sửa đúng** (đẻ ra một mã chết nhỏ, finding #2) | xem 3.5 |
| 6 | Nit LOG-08 — đừng lách phép kiểm mẫu | **đã sửa đúng** (lập luận trong thân commit **sai**, finding #4) | xem 3.6 |
| — | P3 MNT-04 — kích thước gói | **cố ý không sửa, nợ đã ghi đúng** | mục 1 |
| — | Nit MNT-07 — câu "chỉ áp trong phiên này" vào `COPY` | **cố ý không sửa** | spec-fix cho hoãn "khi có dịp sửa file"; không có dòng nợ trong thân commit — xem finding #6 |

### 3.1 Món 1 — lỗi gốc, hai đường

**Đường ghim** (`measurementToolGateway.ts:641-671`):

```ts
try {
  await deps.save({ … });
} catch (error) {                                  // ← lỗi LẦN MỘT, bind ở đây
  if (measurementErrorCodeOf(error).code !== ID_TAKEN_CODE) throw error;
  row = { ...row, ...(await freshIdentity(projectId)) };
  try {
    await deps.save({ … });
  } catch {                                        // ← KHÔNG bind mới
    throw error;                                   // ← vẫn là lỗi lần một
  }
}
```

`catch` trong không khai biến, nên `error` trong scope là **đúng** lỗi lần một; không có binding nào che nó. ✓

**Đường hoàn tác** (`lib/mutations/measurement.ts:183-191`): cùng khuôn, viết bằng `.catch(() => { throw error })` trên promise lần hai, `error` là tham số của `.catch()` bao ngoài. ✓ `postMeasurementToServer` (`:107-110`) ném **nguyên** `result.error`, và `onUndoFailed?.(error)` ở `:199` chuyển tiếp **nguyên**, nên danh tính lỗi đi hết đường không bị bọc lại.

**Phía test — bài kiểm giờ phân biệt được thật.** Đây là chỗ lượt 1 nghi ngờ nhất, và nó đã đứng:

- `measurementToolGateway.test.ts:129-136`: `first = idTaken()` (409) và `second = toAppErrorThrown(httpError(422, 'MEASUREMENT_LIMIT_REACHED'))` là **hai đối tượng khác danh tính** (`idTaken()` là hàm, gọi ra thực thể mới; `toAppErrorThrown` dựng `new Error` mới). Khẳng định là `rejects.toBe(first)` — **so danh tính**, không so mã. Nếu mã ném nhầm lỗi lần hai thì `toBe` đỏ dù `code` có trùng hay không.
- `lib/mutations/__tests__/measurement.test.ts:212-227`: `taken` là hằng mức module; `limit = { ...taken, code: 'MEASUREMENT_LIMIT_REACHED', status: 422 }` là **bản sao nông**, tức một đối tượng khác. Khẳng định `expect(onUndoFailed.mock.calls[0]?.[0]).toBe(taken)` — cũng là so danh tính. Cộng `expect(spy).toHaveBeenCalledTimes(2)` chốt đúng hai lượt ghi.

Hai bài kiểm này **không** còn qua được bằng cách so mã. Finding #1 của lượt 1 đã đóng.

### 3.2 Món 2 — 404 + resource, và **đã kiểm hợp đồng BE, không đoán**

`useMeasurementTool.ts:780-781`: `resource === 'measurement' && code === 'NOT_FOUND'`.

Câu hỏi nguy hiểm là: mã dây BE trả cho 404 có đúng là `NOT_FOUND` không? Nếu BE trả mã khác thì điều kiện mới **chặn cả ca 404 thật** và câu "đã bị xoá ở nơi khác" **không bao giờ hiện**. Tôi tra ba nguồn, không đoán:

1. `backend/prompts/B0-02.md:35` — bảng mã lõi: `NOT_FOUND` **404**.
2. `backend/prompts/B2-07.md:62-68` (chính prompt sở hữu `/measurements`) — "Mã lỗi riêng" chỉ có `MEASUREMENT_ID_TAKEN` 409, `MEASUREMENT_LIMIT_REACHED` 422, `TEMPLATE_LIMIT_REACHED` 422. Dòng sau: "Mã lõi: `NOT_FOUND` 404 (`resource:"project"` hoặc `"measurement"`)". **Không có mã 404 riêng cho phép đo.**
3. `F-02.md` khối [2] #18 — `DELETE …/measurements/{id}` → 204 · lỗi FE xử lý: 404 `resource:"measurement"`.

Thêm một lớp an toàn có sẵn: kể cả khi BE trả 404 **không kèm** `code`, `lib/errors/kinds.ts:91` đặt mã dự phòng của `kind: 'notFound'` đúng bằng `'NOT_FOUND'`, và `toAppError.ts:13` ánh xạ status 404 → `notFound`. Nên cả hai hình dạng lỗi (`HttpError` thô và `AppError` mà `mutateAsync` ném) đều ra `code: 'NOT_FOUND'`.

**Không có lượt mạng thừa.** Ca 403 mới (`useMeasurementTool.test.tsx:474-490`) đếm số lượt GET qua `stubServer(...).lists()` và khẳng định nó **không đổi**; ca 404 khẳng định nó **tăng**. Trước vòng sửa, một 403 mang `resource: "measurement"` sẽ hiện sai câu **và** tốn một `invalidateQueries`. Hai ca này chặn đúng chỗ đó. Cả hai chạy trên **cổng thật** (`renderRealGateway`, chỉ giả `fetch`), không phải cổng mẫu.

### 3.3 Món 3 — bản nháp đếm điểm thật

`useMeasurementTool.test.tsx:341-374`: `measureTwoPoints()` gọi **một lần**, trước lượt ghim đầu. Ghim lần một hỏng (422), rồi ghim lần hai **không** bắt điểm lại; khẳng định `saved[0]?.points` có **2** điểm và `saved[1]?.points` **bằng** `saved[0]?.points`. Bản nháp mất một điểm thì `saved[1]` dài 1 và khẳng định đỏ. Đúng như tên ca hứa. ✓

### 3.4 Món 4 — bốn dòng nối

Đúng bốn chỗ, mỗi chỗ một dòng, thuần trắng khoảng, không đổi hành vi:
`CadBranchConfirm.test.tsx:133` · `useCadBranchConfirm.test.ts:85` · `ScaleCalibration.test.tsx:203` · `useScaleCalibration.test.ts:113`. ✓ (ranh giới: finding #5)

### 3.5 Món 5 — câu tiếng Việt thay chuỗi kỹ thuật

`useScaleCalibration.ts:626`: `throw new Error('chưa lưu được tỉ lệ, máy chủ chưa hỗ trợ')`. Viết thường, kiểu câu, không mã lỗi trần — **A6 đạt**, khối [9] đạt. Nhánh này hôm nay vẫn chết (guard `!supports.persistScale` ở `:613` chặn trước), đúng như spec-fix ghi. ✓

### 3.6 Món 6 — không lách phép kiểm mẫu

`measurementToolGateway.ts:548-564`. Mã mới **đúng**, nhưng lý lẽ tác giả viết trong thân commit thì **sai** — đây là chỗ tôi soi kỹ nhất vì nó là chỗ dễ vỡ nhất của vòng sửa.

Tác giả khai bỏ `wire?.resource` ở nhánh sau "vì nhánh đó chỉ chạy khi `wire === null`". **Không đúng:** trước vòng sửa điều kiện là `wire?.code !== undefined`, nên một `HttpError` có `code` **không qua mẫu** (`wire !== null` nhưng `wire.code === undefined`) **vẫn** rơi xuống nhánh sau — đó chính là ca mà món 6 sinh ra để sửa.

Nhưng **hệ quả thì không xấu**, và món 2 **không** hỏng lặng lẽ, vì nhánh đầu mới giữ nguyên `resource`:

```ts
if (wire !== null) return { code: wire.code ?? null, resource: wire.resource ?? null };
```

Đường duy nhất mất `resource` sẽ là: một lỗi **vừa** qua `isHttpErrorShape` (`wireError.ts:39-44`: có `kind`, `requestId`, `retryable`, **và** khoá `raw`) **vừa** mang `params.resource` mà `raw.resource` lại vắng. `HttpError` không có trường `params`; và `AppError` bị `isAppErrorShape` loại đích danh bằng `!('raw' in value)` (`wireError.ts:47-53`), `toAppError` cũng không dựng `raw`. Tôi kiểm cả `toAppErrorThrown` của chính file test (`:59-61`): `Object.assign(new Error(…), toAppError(error))` — **không** có `raw`, nên nó đi nhánh `AppError` như trước. **Không có đường nào mất `resource`.** ✓

Mã mới cũng không làm hỏng người đọc nào: ba nơi gọi (`useMeasurementTool.ts:770`, `:780`, `measurementToolGateway.ts:657`) đều tra theo khoá UPPER_SNAKE, không nơi nào sống nhờ một `code` tự do.

---

## 4. Finding mới của vòng sửa

Không có **P0**, không có **P1**. Không finding nào **chặn gộp**.

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P3** | TEST-04 | Ca 403 chứng minh "không làm mới danh sách" bằng một lượt **ngủ theo đồng hồ thật** 50 ms, trong một file **không** cài đồng hồ giả. Chứng minh phủ định bằng cách chờ không chắc theo cả hai hướng: máy chậm thì 50 ms chưa đủ để lượt GET kịp xuất hiện (âm tính giả), máy nhanh thì đó là 50 ms lãng phí mỗi lượt chạy. Và chính bộ test này vừa cho thấy máy **có** lúc chậm (mục 2.2) | `src/screens/viewer/MeasurementTool/useMeasurementTool.test.tsx:487` | Bỏ lượt ngủ. `renderWithProviders` **trả về** `queryClient` của chính lượt dựng (`lib/testing/render.tsx:253`), nên: `const { queryClient } = renderRealGateway({ notifications }); const spy = vi.spyOn(queryClient, 'invalidateQueries');` rồi bấm xoá và khẳng định `spy).not.toHaveBeenCalled()`. `invalidateQueries` được gọi **đồng bộ** ngay sau `publish`, trong cùng khối `catch` (`useMeasurementTool.ts:783` và `:790`), nên sau `waitFor(notifications…)` là đã chắc chắn quyết định xong — không cần chờ thêm mili-giây nào |
| 2 | **P3** | MNT-02 | Món 5 lấy đi **người đọc cuối cùng** của `missingEndpoint`. Sau vòng sửa, `grep -rn "missingEndpoint" src/` chỉ còn ba dòng **ghi** (`:78` bảng, `:91` khai trường, `:104` gán) và **không** dòng nào đọc. Một trường mà không ai đọc sẽ trôi khỏi sự thật mà không ai biết | `src/screens/pipeline/ScaleCalibration/scaleCalibrationGateway.ts:78,91,104` | Hoặc xoá trường `missingEndpoint` khỏi `ScaleUnsupported` cùng bảng `SCALE_MISSING_ENDPOINTS` (giữ `capability`, thứ vẫn có người đọc ở `usePipelineFailure.test.ts:161`), hoặc giữ lại kèm một dòng chú thích nói rõ nó là **tài liệu**, không phải dữ liệu chạy |
| 3 | **Nit** | TEST-06 | Ca mới của món 6 chỉ khẳng định `.code` là `null`, **không** khẳng định `.resource` vẫn còn — mà nhánh vừa đổi (`wire !== null`) đúng là nhánh duy nhất đọc `resource` cho `HttpError`, và đúng là thứ món 2 dựa vào. Lập luận ở 3.6 cho thấy hôm nay không mất, nhưng không có bài kiểm nào ghim điều đó | `src/screens/viewer/MeasurementTool/measurementToolGateway.test.ts:219-222` | Thêm một dòng vào chính ca đó: cho `odd.raw` thêm `resource: 'measurement'` rồi `expect(measurementErrorCodeOf(odd)).toEqual({ code: null, resource: 'measurement' })` |
| 4 | **Nit** | MNT-08 | Lý lẽ trong thân commit `b2fccb1` cho món 6 ("nhánh đó chỉ chạy khi `wire === null`") **sai** — xem 3.6. Mã đúng, lời giải thích sai; người sửa sau đọc nó sẽ tin nhầm về hình dạng lỗi đi qua hàm này | thân commit `b2fccb1` | Sửa lại lời khi có dịp: nhánh cũ **có** chạy với `wire !== null && wire.code === undefined`; nhánh mới giữ `resource` chính là để ca đó không mất gì |
| 5 | **Nit** | R-27 | Khối **[12]** của F-02 cho sửa test của F-06 "**chỉ khối ghi nhớ**" — khối đó là `describe` ở `useCadBranchConfirm.test.ts:550`. Dòng sửa nằm ở `:85`, trong `afterEach` toàn cục, **ngoài** khối ấy | `src/screens/pipeline/CadBranchConfirm/useCadBranchConfirm.test.ts:85` | **Không chặn gộp**: `spec-fix.md` mục 4 ra lệnh đích danh sửa đúng dòng này, và thay đổi là thuần trắng khoảng, không đổi hành vi. Ghi lại để F-06 biết khi rebase (F-02 gộp trước, F-06 rebase — `F-02.md` [1]) |
| 6 | **Nit** | R-34 | Nit MNT-07 (đưa câu "tỉ lệ chỉ áp trong phiên này" vào `COPY`) được hoãn nhưng **không** có dòng nợ trong thân commit, khác với MNT-04. Hai món hoãn, một món có nợ ghi, một món không | thân commit `b2fccb1` | Thêm một dòng nợ khi có dịp, hoặc làm luôn — nó là một hằng chuỗi |
| 7 | **Nit** | OBS-03 | `catch { throw error }` **vứt** lỗi lần hai không để lại dấu vết nào. Nếu lượt ghi lại hỏng vì lý do khác hẳn (422 hết hạn mức, 403), người dùng và log chỉ thấy 409 của lần một | `measurementToolGateway.ts:665`, `lib/mutations/measurement.ts:189` | Trần đã biết: lỗi lần hai không quan sát được. Nếu muốn giữ cả hai mà không đổi danh tính: `catch (second) { throw Object.assign(error, { cause: second }) }` — nhưng nó **sửa** đối tượng lỗi gốc, nên đây là gu, không phải lỗi. Để nguyên cũng đứng được |
| 8 | **P3** | TEST-07 | `pnpm verify` bước 4 **không xanh ổn định** ở máy này: 3 đỏ / 4 lượt, toàn bộ là hết giờ, lượt thứ tư xanh sạch. Ba ca dính đều dựa vào `React.lazy` + `Suspense` với trần 4000/5000 ms, và trần đó không chịu nổi 340 file chạy song song khi máy bận. **Không** quy được cho F-02 (mục 2.3), nhưng là một cổng lung lay mà người sau sẽ tốn giờ vì nó | `Viewer3DPanels.test.tsx:94,161` · `Viewer3DOverlays.test.tsx:24` · `MobileViewer.container.test.tsx` · `VersionHistory.test.tsx` | **Ngoài phạm vi F-02 — đừng sửa trong nhánh này.** Việc cho một prompt sau: nâng `testTimeout`/`LAZY_WAIT` cho các bộ có panel `lazy`, hoặc bật `retry` riêng cho chúng. Lưu ý: nâng một trần **chờ** không phải là hạ một ngưỡng **chất lượng** (K24) — hai thứ khác nhau |

---

## 5. Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 | 0,28 |
| OBS, OPS – Vận hành | 5 % | 4 | 0,20 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |
| **Tổng** | **100 %** | | **4,85 / 5** |

Ghi chú điểm so với lượt 1 (4,58): **LOG 4 → 5** vì hai món đúng-sai thật (E3 lỗi gốc, E4 cổng 404) nay khớp hợp đồng BE đã tra tận nguồn; **RES 4 → 5** vì danh tính lỗi đi hết đường không bị nuốt; **TEST 3 → 4** vì hai khẳng định rỗng/yếu mà lượt 1 nêu đã thành khẳng định danh tính và khẳng định số điểm, trừ lại một bậc cho lượt ngủ 50 ms (#1) và khẳng định `resource` còn thiếu (#3); **OBS 5 → 4** cho lỗi lần hai bị vứt (#7) và cổng lung lay (#8); **MNT giữ 4** — sửa được bốn dòng nối nhưng đẻ ra một trường chết (#2) và một lời giải thích sai (#4).

---

## PHÁN QUYẾT: APPROVE

**Sáu trên sáu món đã sửa đúng, không món nào sửa nửa vời.** Chỗ lượt 1 nghi ngờ nhất — bài kiểm "ném lại lỗi gốc" có thật sự phân biệt được không — nay dùng **hai đối tượng lỗi khác danh tính** và khẳng định bằng `toBe(lỗi_lần_một)` trên cả hai đường, nên nó đỏ được khi mã sai. Chỗ dễ vỡ nhất — món 6 kéo theo đổi hành vi mà spec không đòi — tôi đã truy hết: lập luận của tác giả **sai** nhưng mã **đúng**, và **không có đường nào** làm mất `resource` của một `HttpError`, nên món 2 không hỏng lặng lẽ. Mã dây 404 mà món 2 rẽ nhánh theo đã tra tận `B2-07.md:62-68` và `B0-02.md:35`: `NOT_FOUND` là đúng, `/measurements` không có mã 404 riêng, và FE còn có một lớp dự phòng ở `kinds.ts:91`.

**Không có finding nào phải sửa trước khi gộp vào `master`.** Tám finding mới đều là P3 và Nit; bảy trong số đó là việc dọn khi có dịp, và #8 nằm ngoài phạm vi F-02.

**Về cổng.** Tôi **không** ký "`pnpm verify` 7/7 trong một lượt" — hai lượt verify của tôi đều dừng ở bước 4. Nhưng tôi đã tự chạy từng bước và **thấy cả bảy đều đạt**, gồm một lượt `pnpm coverage` sạch (340/340 file, 7136/7136 test, mã thoát 0, ngưỡng độ phủ đạt) và `build`/`size`/`length` mã thoát 0. Hai lượt đỏ là flake hết giờ trên đường mã mà **cả nhánh** không chạm, tập ca đỏ đổi mỗi lượt, xanh khi chạy riêng, và nền (`master`, `338242a`) cũng xanh — mục 2.3 ghi đủ, kể cả điều tôi **không** kết luận được vì hai nhóm lượt chạy không cùng điều kiện. Người gộp nên cầm **một** lượt cổng xanh (tại máy hoặc job `unit` của CI) trước khi bấm merge — đó là thủ tục của phiên gộp, không phải việc sửa mã của tác giả.

Về `pnpm e2e` **không chạy lại**: tôi đồng ý với quyết định đó. Diff vòng sửa chỉ chạm MeasurementTool, ScaleCalibration và CadBranchConfirm; không dòng nào đi vào đường dựng 3D mà `viewer3d.spec.ts` soi, và lượt 1 đã chứng minh hai ca đỏ ở đó hỏng y hệt trên `master` `b06acc5`. Chạy lại sẽ tốn thời gian để ra đúng câu trả lời cũ.
