# Review merge `feature/f-02-go-mock-va-luu-gia` → `master` (AppFront)

- Ngày: 2026-09-25 · Reviewer: phiên `/merge-review` (worker Orca, worktree riêng `f-02-review`)
- Repo: `F:/AppFront` · Commit đầu nhánh: `338242a03b39` · Nền: `master` `b06acc5956b6`
- Prompt: `F:/AppBack/backend/prompts/F-02.md` · Diff: 35 file, 6 file mới, 5 commit (4 việc + 3 merge `--no-ff` + 1 commit gộp)
- Cổng: `pnpm verify` mã thoát **0** — log `C:/Users/mxuan/AppData/Local/Temp/claude/f02rev-verify1.log`
- Độ phủ: `src/domain/measure/measure.ts` **94,14 %** dòng / 91,22 % nhánh · `src/lib/mutations/measurement.ts` **100 %** dòng / **90,47 %** nhánh

---

## 1. Điều kiện dừng sớm — không cái nào chạm

| Điều kiện | Kết quả |
|---|---|
| Cây làm việc bẩn | `git status --porcelain` rỗng trước và sau mọi lệnh ✔ |
| Dòng đầu commit / trailer `Prompt: F-02` | 4 commit việc + commit gộp đều có trailer. Dòng đầu của `338242a` là `F-02: gỡ mock và lưu giả` — **không** Conventional, nhưng đó là chuỗi prompt [11].7 ra lệnh viết nguyên văn. Không tính là vi phạm ✔ |
| Chạm khối [12] (`src/api/**`, `src/routes/**`, `src/store/**`, `src/lib/{http,auth,autosave,query}/**`, `useCadBranchConfirm.ts`, `vitest.config.ts`, `eslint-rules/**`, `package.json`, `scripts/**`) | `git diff --name-only master...HEAD` lọc theo toàn bộ danh sách → **0 file**. `useCadBranchConfirm.ts` nguyên vẹn (chỉ file test của nó đổi, đúng phần được phép) ✔ |
| `@ts-ignore` · `@ts-expect-error` · `as unknown as` · `eslint-disable` · `it.skip`/`it.todo`/`.only` mới | grep trên **dòng thêm** của diff → **0** ✔ |
| Hạ ngưỡng độ phủ | `vitest.config.ts` không nằm trong diff ✔ |
| `changes/<mã>.md` | Không áp dụng cho AppFront (theo chỉ dẫn điều phối) |

Mảnh `.orca-notes/F-02-T*-i18n.fragment.md`: **không còn**. (`.orca-notes/` còn các mảnh S13/S14/S15/T1–T6 của những prompt trước — có sẵn trên `master`, ngoài diff này.)

---

## 2. Bằng chứng cổng — tự chạy lại, không lấy số tác giả

### 2.1 `pnpm verify` — 7/7 ĐẠT ngay **lượt đầu**

```
đạt  typecheck · đạt  lint · đạt  import vòng · đạt  test + độ phủ
đạt  build     · đạt  kích thước gói · đạt  độ dài file
Tất cả các bước đều đạt.                                   EXIT=0
```

- Bước 4: **340 file test · 7133 / 7133 test qua** (115,4 s) — khớp đúng số tác giả khai.
- Bước 7: **343 file quét · 59 vượt mốc nhắc 250 · 0 vượt trần 400**. `Viewer3D.container.tsx` = **386 dòng** (trước: 397) ✔

**Khẳng định biện hộ #2 của tác giả — ĐÚNG.** Tác giả khai `Viewer3DPanels.test.tsx:161` đỏ ở lượt đầu vì hết giờ `waitFor` dưới tải cả bộ, không phải hồi quy. Ở máy này bộ đầy đủ xanh **ngay lượt đầu**, và `Viewer3DPanels.test.tsx` **không** nằm trong diff (`git diff --name-only` không có nó). Không có file nào đỏ vì thiết kế.

### 2.2 `pnpm size` — TĂNG, nhưng cổng vẫn đạt

| Đại lượng | master (tác giả khai) | đo lại ở `338242a` | ngân sách | phán quyết |
|---|---|---|---|---|
| màn hình đầu (chunk vào + nhập tĩnh) | 162,4 KiB | **163,0 KiB** | 175 | đạt (dư 12,0) |
| chunk JS lớn nhất | 162,4 KiB | **163,0 KiB** | 170 | đạt (dư 7,0) |
| chi phí thêm một màn | — | 264,2 KiB | 280 | đạt |
| tổng CSS | 10,9 KiB | **10,9 KiB** | 12 | đạt |
| tổng JS mọi chunk | 1062,9 KiB | **1065,0 KiB** | 800 (mốc **cảnh báo**) | QUÁ MỐC — *không* đổi mã thoát |

`scripts/check-bundle-size.mjs:454-470` khai rõ tổng JS là **cảnh báo in ra, không góp vào `over`, không đổi mã thoát**; `master` cũng đã quá mốc. Nên bước 6 đạt thật, không phải đạt nhờ nới. Số tác giả khai khớp từng dòng.

### 2.3 `pnpm e2e` — 13 qua / 2 hỏng, và **hỏng y hệt trên `master`**

**Khẳng định biện hộ #1 của tác giả — ĐÚNG, tự kiểm hai lượt.**

| Lượt | Kết quả | Ca hỏng |
|---|---|---|
| `338242a` (nhánh) | 13 passed · 2 failed (57,5 s) | `viewer3d.spec.ts:479` ViewCube (P2) · `viewer3d.spec.ts:521` tìm phòng (Q2) |
| `b06acc5` (`master`, checkout tách rời trong chính worktree này) | 13 passed · 2 failed (1,4 m) | **đúng hai ca đó, không nhiều không ít** |

Nguyên nhân ở cả hai lượt là `subtree intercepts pointer events` (lớp phủ `pointer-events-auto fixed bg-bg-overlay` và `<span aria-label="Người dùng thử">` chặn click), **không** phải lệch ảnh chuẩn `win32`/`linux`. → Hai ca này là nợ có sẵn của `master`, **không** phải hồi quy của F-02. Worktree đã trả về nhánh và `git status --porcelain` rỗng sau lượt kiểm.

### 2.4 Hai lệnh nghiệm thu [11].5 — tự chạy lại

```
git grep -n "mockApiClient" -- src/screens ':!*.test.*' ':!*.stories.*'      → 0 dòng (master: 12) ✔
git grep -n "persistedScales\|persistedBranchChoices" -- src/screens/pipeline → 0 dòng ✔
git grep -n "isRememberedChoiceSessionOnly\|readPersistedScale\|clearPersistedScales\
             \|readPersistedBranchChoice\|clearPersistedBranchChoices" -- src/  → 0 dòng ✔
```

---

## 3. Soát theo miền — những chỗ prompt gọi tên

### A — sáu cổng mặc định về client thật ✔
Sáu file đổi `?? mockApiClient` → `?? createAppApiClient()` và gỡ nhập `@/api/__mocks__/client`. Không đường sản phẩm nào còn đọc mock.

**Test có lặng lẽ rơi vào client THẬT không — đã soát, KHÔNG.** Repo không có `.env`, nên trong vitest `resolveUseMockApi()` trả `false` và `createAppApiClient()` là client thật. Đã kiểm từng nơi gọi:
- bốn hook QC dùng `useResolvedGateway`: `if (injected !== undefined) return injected;` **trước** `fallbackRef.current ??= createXGateway()` (`useDimensionOcrReview.ts:318-330`), và mọi `mountHook` đều tiêm `gateway: options.gateway ?? createMockXReviewGateway()`;
- `useDimensionOcrReview.test.ts:282` và `mobileViewerGateway.test.ts:50,58` — hai chỗ trước đây gọi mặc định — nay tiêm `createMockApiClient()` tường minh;
- hai ca hook mới ở `useMeasurementTool.test.tsx` **cố ý** chạy cổng thật, và giả `fetch` bằng `vi.stubGlobal` trước khi render, gỡ bằng `vi.unstubAllGlobals()` ở `afterEach`. Đây là "tiêm đúng", không phải "xanh vì `fetch` không tồn tại".

Không có test nào xanh nhờ lý do sai.

### B — nhà mẫu chỉ sống ở chế độ mock ✔ (hành vi), ⚠ (kích thước — xem P3-1)
`shouldUseViewerFixture()` là hàm thuần có test đủ bốn ca; `defaultViewerShellGateway(useMock)` tách ra được và có test cả hai nhánh. `Viewer3D.container.tsx` ngắn đi 11 dòng.

### C — không gửi đồ thị mẫu ✔
Cả **hai** cổng: `objectLayerReviewGateway.ts:1932-1940` và `dimensionOcrReviewGateway.ts:1195-1203` (chỗ kế hoạch gốc bỏ sót). `graph.read()` gọi **đúng một lần** rồi dùng lại; `null` → `Promise.resolve(unsupported(...))`, **không** gọi `persist*`. Đọc `createOptimisticMutation.ts:51-59`: `supported:false` đi đường `afterSuccess`, nên **không** `rollback`, không ném, không toast đỏ — đúng [4].C. Hai file test mới khẳng định đúng ba điều đó.

### D — Map "đã lưu" giả → `supports.* = false` ✔
- `persistedScales`, `persistedBranchChoices`, `readPersisted*`, `clearPersisted*`, `isRememberedChoiceSessionOnly` **biến mất hết** khỏi `src/`.
- Bản mock CAD giữ `rememberChoice: true` nhưng nhớ trong **closure của từng cổng** (`cadBranchConfirmGateway.ts:774`), và có test riêng "hai cổng mock dựng riêng không thấy lựa chọn của nhau".
- **Câu chữ khi năng lực tắt đúng A5/A8:** `saveText` = `'tỉ lệ chỉ áp trong phiên này, chưa lưu lên máy chủ'` — trung tính, không hứa "đã lưu". `isApplying` có thêm điều kiện `gateway.supports.persistScale` nên nút **không quay mãi**; có test khẳng định cả ba.
- Đã soát riêng đường A7: `saveLabel` của `useAutosave` **không** được xuất ra model (chỉ là phụ thuộc của `useMemo`, `useScaleCalibration.ts:1559`), `useSaveIndicator` không gắn ở màn này, và `ConnectedSaveIndicator` không được render ở đâu cả. Nên nhãn "Đã lưu lúc …" giả **không** lọt ra màn hay ra trình đọc màn hình.

### E1 — id và `Set` mã đã xoá ✔
- `nextMeasurementNoteSequence` (`measure.ts:503-522`): một vòng `O(n)` dựng `Set` + `highest`; dưới trần → `highest + 1`; **chạm trần → số dương nhỏ nhất chưa dùng**, vòng `while` tối đa `n+1` bước trên danh sách ≤ 1000. **Không** `O(n²)`.
- `readMeasurementNoteSequence` trả `null` cho số không `Number.isSafeInteger`. Đã soát "có chỗ nào coi `null` là `0` rồi cấp lại id 1 không": chỉ `nextMeasurementNoteSequence` đọc nó, và ở đó `null` bị **bỏ qua** chứ không thành `0`. Trần 15 chữ số (`999_999_999_999_999`) nhỏ hơn `MAX_SAFE_INTEGER` (≈ 9,007 × 10¹⁵), nên mọi id hợp lệ luôn là số an toàn — nhánh `null` không với tới được từ dữ liệu máy chủ hợp lệ.
- `Set` nằm trong closure của `createMeasurementToolGateway` → **mỗi cổng một `Set`** ✔. `saveMeasurement` gặp id thuộc `Set` thì trải `nextMeasurementIdentity(...)` lên bản ghi — hàm này trả **cả `id` lẫn `name`**, nên **tên được sinh lại cùng id**, không dính tên cũ ✔ (test `saved.name === 'Phép đo 4'`).
- `deletedIds.add(id)` đặt **sau** `await deps.remove(...)`, nên lượt xoá hỏng không ghi nhầm id vào `Set` ✔.

### E2 — `safeParseList` ✔
`decode.ts:206-223` xác nhận: ném chỉ khi `invalidRatio > 0.2` (**vượt**, không phải bằng); dưới ngưỡng thì hàng hỏng bị bỏ im lặng. Chỗ gọi có đúng `if (!decoded.ok) throw decoded.error` (`measurementToolGateway.ts:612-614`). Ca test "vượt ngưỡng" dùng **3 hỏng / 5 hàng = 60 %**, vượt thật ✔.

### E3 — thử lại đúng một lần ✔ (một lệch nhỏ — xem P2-1)
409 `MEASUREMENT_ID_TAKEN` → `http.get` **1** lần, `save` **2** lần, id lần hai = lớn nhất + 1 của danh sách mới. 422 `MEASUREMENT_LIMIT_REACHED` → ném ngay, `save` 1 lần, **không** đọc lại. Cả ba có test.

`measurementErrorCodeOf` xử được **cả hai** hình dạng — đã kiểm bằng mã nguồn, không chỉ bằng test: `fromHttpError` truyền `code: error.code` vào `resolveCode` (`toAppError.ts:220-221, 265-273`) nên `AppError.code` giữ nguyên mã dây, và `readWireError` trả `null` với `AppError` (`wireError.ts:88-91`) → nhánh thứ hai của hàm đọc `error.code` + `params.resource`. Đúng như prompt mô tả.

### E4 — lỗi hiện ra đúng một lần, bản nháp không mất ✔
- `onPin` nay `.then(clearDraft)`: bản nháp chỉ bị bỏ khi `saveMeasurement` **xong**; hỏng thì điểm còn nguyên ✔.
- **Một** thông báo cho một lần hỏng: `saveMeasurement` mutation không có `onError` phát thông báo nào khác, chỉ `catch` của hook phát ✔ (test khẳng định `notifications.list()` có đúng 1 phần tử).
- **Không** in mã lỗi trần: bảng `MEASUREMENT_ERROR_TEXT` + hai câu dự phòng, có test `not.toContain('SOMETHING_ODD')` ✔.
- Câu tiếng Việt **viết thường, kiểu câu** (A6) ✔ — đã đọc cả 7 câu.

### E5 — ranh giới import và vòng nhập ✔
- Bước 3 của `pnpm verify` (`import/no-cycle`) **đạt** → không có đường nhập ngược.
- `src/lib/mutations/measurement.ts` **không** nhập `src/screens`: nối bằng `MeasurementMutationDeps.resolveUndoConflict?` dựng ở hook qua `httpGatewayRef` (`useMeasurementTool.ts:330-352`) ✔.
- Cổng **được tiêm** thì `injectedGateway === true` → khoá `resolveUndoConflict` **vắng khỏi deps**, và `undo()` cho 409 đi thẳng `onUndoFailed` chứ không nổ ✔ (test `'sends a 409 straight to onUndoFailed when nothing resolves conflicts'`, `spy` đúng 1 lần).
- `.catch(() => undefined)` đã bỏ, `.finally(applyInvalidation)` còn nguyên ✔.

### E6 — nhãn nhật ký ✔ (quyết định đã chốt, không phải finding)
`ACTIVITY_KIND_LABELS` giữ **27** khoá của `master`. `vi.json` `userManagement.activity` nay **28** khoá (27 + `fallback`): 11 khoá cũ đã được thay, `wallEdit` mất, `trainingCancel` có. JSON hợp lệ (bước typecheck/test đọc được). `activityKindLabel` là hàm thuần và `useUserManagement.ts:864` đã gọi nó thay vì tra bảng tại chỗ ✔.

### Bảy trạng thái (A11) ✔ — không màn nào rơi vào trắng
Đã truy đường rỗng của bản dựng sản phẩm: `useViewerShell.ts:573-574` — `data.storeys.length === 0` → **`'empty'`**, không phải màn trắng. `Viewer3D` không có nhà mẫu thì `resolvedSpatial = null` và cổng là cổng đọc kho, rơi vào cùng nhánh ấy. `expectSevenStates` của các màn liên quan đều còn xanh trong bước 4 (log in `expectSevenStates: 7/7`).

---

## 4. Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P2** | TEST-03 / LOG-06 | Lượt ghi thứ hai ném **lỗi lần hai**, không phải lỗi gốc như [4].E3 ra lệnh — và bài kiểm mang tên "ném lại lỗi gốc" **không kiểm được điều đó**: `mockRejectedValue(idTaken())` gọi `idTaken()` một lần nên cả hai lượt từ chối trả **cùng một đối tượng**, "gốc" và "lần hai" trùng nhau. Cùng lệch ở đường hoàn tác. | `measurementToolGateway.ts:659-660` · `measurementToolGateway.test.ts:127-137` · `lib/mutations/measurement.ts:186-191` | Chọn một: (a) bọc lượt thứ hai `try { … } catch { throw error }` cho khớp prompt; hoặc (b) giữ hành vi hiện tại — nó **thực dụng hơn** (422 hết hạn mức ở lần hai hiện đúng câu giới hạn thay vì câu 409) — nhưng **đổi tên test** và ghi vào "Lệch khỏi prompt". Không được để nguyên cả hai. |
| 2 | **P3** | MNT-04 | Nhà mẫu vẫn **nằm trong gói sản phẩm**: `VIEWER_FIXTURE_SPATIAL` và `createViewerShellFixtureGateway` còn là **nhập tĩnh** trên đường luôn chạy, nên Vite không rụng được chúng. `pnpm size` **tăng** 162,4 → 163,0 KiB, tổng JS 1062,9 → 1065,0. Phần B đạt về **hành vi**, chưa đạt về **kích thước**. | `useViewer3DSource.ts:7-9` · `useViewerShell.ts:90` | Không chặn — prompt [4].B chỉ đòi cổng theo `resolveUseMockApi()`, và tác giả không hứa đã gỡ khỏi gói. Nhưng chính `check-bundle-size.mjs:472-474` in lời khuyên "đưa fixture/mock ra khỏi gói sản phẩm". Ghi một dòng nợ cho prompt sau (`import()` động sau cờ mock). |
| 3 | **P3** | LOG-07 | "Đã bị xoá ở nơi khác" chỉ dựa vào `resource === 'measurement'`, **không** kiểm status 404 như [4].E4 mô tả. Một 403 hay 409 mang `resource: "measurement"` sẽ hiện câu sai và gọi thêm một lượt `invalidateQueries` thừa. | `useMeasurementTool.ts:780` | Thêm điều kiện status/mã: `code === 'NOT_FOUND' && resource === 'measurement'`. |
| 4 | **P3** | TEST-05 | Bài kiểm `'bản nháp còn đủ điểm sau khi ghim hỏng'` chỉ khẳng định nút "ghim" **còn tồn tại**, không đếm điểm của bản nháp. Tên hứa nhiều hơn phép kiểm — bản nháp mất một điểm vẫn qua. | `useMeasurementTool.test.tsx:341-360` | Khẳng định thẳng số điểm của bản nháp (hoặc nhãn độ dài đang hiện), không chỉ sự tồn tại của nút. |
| 5 | **P3** | MNT-02 | Bốn chỗ bị nối hai câu lệnh vào một dòng khi xoá `clearPersisted*` — dấu vết sửa bằng máy, `lint` không bắt nhưng đọc khó. | `CadBranchConfirm.test.tsx:133` · `useCadBranchConfirm.test.ts:85` · `ScaleCalibration.test.tsx:203` · `useScaleCalibration.test.ts:113` | Tách lại hai dòng. |
| 6 | Nit | MNT-06 | `throw new Error(result.missingEndpoint)` ném chuỗi kỹ thuật `'PUT .../spatial/layer — F-04c'`. Hôm nay là **nhánh chết** (guard `!supports.persistScale` ở `:613` chặn trước) và `saveText` đã che `saveLabel`, nên không tới người dùng — nhưng nếu ai nối `saveLabel` vào một chỉ báo chung thì chuỗi này lọt ra. | `useScaleCalibration.ts:626` | Ném một `Error` có câu tiếng Việt, hoặc bỏ `missingEndpoint` khỏi thông điệp. |
| 7 | Nit | MNT-07 | Câu `'tỉ lệ chỉ áp trong phiên này, chưa lưu lên máy chủ'` viết thẳng trong hook, trong khi mọi câu khác của file đi qua `COPY`. Prompt chỉ định đúng chuỗi này nên không sai, chỉ lệch khuôn. | `useScaleCalibration.ts:1518-1520` | Đưa vào `COPY` của cùng file khi có dịp sửa file. |
| 8 | Nit | LOG-08 | `measurementErrorCodeOf`: khi lỗi **có** hình dạng `HttpError` nhưng `code` không qua được mẫu UPPER_SNAKE, hàm rơi xuống nhánh `AppError` và đọc thẳng `error.code`, **bỏ qua** phép kiểm mẫu mà `readWireError` cố tình đặt ra. | `measurementToolGateway.ts:552-560` | Trả `{ code: null, … }` khi `readWireError` đã nhận ra hình dạng dây mà không đọc được mã. |

**Không có P0. Không có P1. Không có finding nào chặn merge.**

---

## 5. Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 4 | 0,40 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 3 | 0,21 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |
| **Tổng** | **100 %** | | **4,58 / 5** |

Ghi chú điểm: SEC 5 vì nhánh này **gỡ bỏ** đường giả chứ không thêm bề mặt nào; CON 5 vì mọi trạng thái mức mô-đun đã biến mất và `Set` id đã xoá nằm đúng trong closure từng cổng, thử lại có trần cứng một lần; TEST 3 vì finding #1 (một khẳng định rỗng) và #4 (một khẳng định yếu).

---

## PHÁN QUYẾT: APPROVE

Bốn việc A–E của F-02 làm đúng và làm đủ, kể cả chỗ kế hoạch gốc bỏ sót (`dimensionOcrReviewGateway.ts` phần C). `pnpm verify` đạt 7/7 ngay lượt đầu ở máy này với 7133/7133 test, `pnpm size` nằm trong mọi ngân sách chặn cổng, và hai lệnh nghiệm thu `git grep` đều ra 0 dòng. Mọi con số tác giả khai đã được đo lại và **khớp từng dòng**.

Hai khẳng định biện hộ cho bước đỏ đều **đứng vững**, và đó là phần quan trọng nhất của lượt soát này:

1. `pnpm e2e` hỏng **đúng hai ca** `viewer3d.spec.ts:479` và `:521` trên nhánh — và hỏng **y hệt hai ca đó** khi tôi tự chạy lại trên `master` `b06acc5`. Nguyên nhân là lớp phủ chặn click (`subtree intercepts pointer events`), không phải lệch ảnh chuẩn. **Không phải hồi quy của F-02.**
2. `Viewer3DPanels.test.tsx` **không** nằm trong diff, và bộ test đầy đủ xanh ngay lượt đầu ở máy này. Lượt đỏ của tác giả là chập chờn theo tải, không phải hồi quy.

**Không finding nào phải sửa trước khi gộp vào `master`.** Finding #1 (P2) nên được xử lý trong vòng sửa kế tiếp hoặc ghi thành một dòng nợ: cần chọn dứt khoát giữa "ném lỗi gốc như prompt" và "giữ lỗi lần hai vì nó cho người dùng câu chính xác hơn" — và nếu chọn giữ thì phải đổi tên bài kiểm, vì tên hiện tại khẳng định một thứ mã không làm và test không kiểm. Finding #2 (P3, nhà mẫu còn trong gói) là nợ kích thước nên ghi lại cho prompt sau; nó không thuộc phạm vi mà [4].B ra lệnh.
