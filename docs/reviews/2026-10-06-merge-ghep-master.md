# Review merge merge/ghep-master → master (AppFront) — GHEP-MASTER

- Ngày: 2026-10-06 · Reviewer: phiên /merge-review riêng (R-37), không phải tác giả · Repo: AppFront, worktree `C:/Users/mxuan/orca/workspaces/AppFront/ghep-master`
- Commit đầu nhánh: `81ad915440ea` (FIX-382, chỉ chú thích) ← `cbfdbaae0115` (commit gộp; cha 1 `8c28ef961eee` e2e/integrate, cha 2 `585b13806083` master)
- Cổng: phạm vi **đầy đủ dùng lại của tác giả** trên `cbfdbaae` + **đích** cho `81ad9154`. `pnpm install --frozen-lockfile && pnpm verify` mã thoát **0**, 7/7 đạt, 420 tệp / 8 750 test (log: `backend/dieu-phoi/chay/GHEP-MASTER/verify-1.log`, dòng 8221-8242). Log không tự in sha; sha xác nhận bằng reflog worktree: HEAD = `cbfdbaae` từ 21:47:32 tới 22:42:07 (+07), log ghi 21:48–22:02 (+07). `cbfdbaae..81ad9154` chỉ đổi 3 dòng chú thích `e2e/viewer3d.spec.ts` (R-33b: đích; tác giả `pnpm typecheck` 0, `pnpm lint` 0 — `fix382-*.log`). Reviewer chạy đích tại chỗ trên `81ad9154`: `pnpm exec vitest run progressStream.test.ts EditorTour.test.tsx refresh.test.ts` → 3 tệp / 66 test, mã thoát 0.
- Độ phủ: ngưỡng vitest (domain 90 % / lib 80 %) đạt theo `verify-1.log`; tổng không in trong log — không chép số.
- e2e (mock): `e2e-1.log` **327 qua / 2 hỏng / 16 bỏ qua**, mã thoát **1** (345 = 323 + 16 mốc e2e/integrate + 6 bài mới của master; bỏ qua không tăng).
- Chuỗi thật F-14 (`chuoi-1.log`): **chưa chạy** — điều kiện [11.3] còn thiếu.

## Đã kiểm (bằng lệnh, không theo báo cáo)
- [11.1] `merge-base --is-ancestor` master và e2e/integrate → `merge/ghep-master`: cả hai 0. [11.2] `git grep -E '^(<<<<<<<|>>>>>>>)'` → 0 khớp.
- [11.4] Mẫu `TODO|FIXME|ponytail:|\.skip\(|\.fixme\(|eslint-disable(?!…)|@ts-ignore|@ts-expect-error`: `git diff 8c28ef96 HEAD` thêm 0 dòng; dòng thêm của `git diff 585b1380 HEAD` không có dòng nào ngoài tập đã có trong `git diff 585b1380 8c28ef96` (comm = 0).
- [12] `git diff 8c28ef96 HEAD -- src/lib/schemas package.json pnpm-lock.yaml vitest.config.ts vendor eslint-rules .github src/routes` rỗng.
- Không mất test: so tiêu đề `it/test/describe` của mọi tệp test bị chạm giữa master, e2e/integrate và HEAD — chỉ hai tiêu đề vắng: "mặc định ở góc trên phải" (đổi thành "mặc định ở giữa cạnh dưới (B-V2-05)", chủ ý), "gỡ công cụ sửa khỏi ray…" (do e2e/integrate `957a711a` bỏ, không do gộp).
- Không nới assert khi đổi nhãn A6: `e2e/editor-tour-chip.spec.ts` (4 dòng) chỉ đổi chuỗi nhãn, giữ `exact: true`; `EditorTour.test.tsx` khối NO-208 đổi nhãn + đảo đối xứng cặp mặc định/override (mặc định khẳng định `bottom-[16px] left-1/2 -translate-x-1/2`, override khẳng định có `right-[16px] top-[16px]` và KHÔNG còn `bottom-[16px]`) — cùng độ chặt như bản master.
- NO-154 trên mã F-05b: `src/lib/realtime/progressStream.ts` = bản master (chốt `refreshedSinceOpen`, gọi `refreshThenRetrySse` một lần khi `sseFailures >= SSE_FAILURE_LIMIT`, mở lại khi `da-noi`); `processingGateway.ts:826` truyền `refreshAuth` vào lời gọi `createProgressStream` duy nhất (luồng quay vòng `pollProgress` không qua SSE nên không cần). Test NO-154 xanh (chạy lại tại chỗ).
- NO-209 + F-01b: `refresh.ts`/`types.ts`/`refresh.test.ts` = bản master; không bộ đọc `expiresIn` nào khác trong `src` (chỉ bộ mẫu `__mocks__/client.ts`, đi qua `defaultParseRefreshResponse`); luồng phiên F-01b (`session.ts`, `bootstrap.ts`, `state.ts`) không bị gộp chạm. `refresh.test.ts` 30/30 xanh tại chỗ.
- 9 tệp xung đột: cách giải đúng như `xung-dot.md` (đối chiếu `git diff 8c28ef96 HEAD` và `git diff 585b1380 HEAD`). `useViewerShell.ts` `instanceof FlatCameraMode/OrbitCameraMode` tương đương duck-typing cũ (`modes.ts`: chỉ Orbit có `dolly`, chỉ Flat/Top/Elevation có `zoom`, Walk không có cả hai).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | TEST / R-58 | [11.3] chưa đạt: `pnpm e2e` mã thoát 1 (2 hỏng). Lời phân loại "có sẵn trên e2e/integrate" của **NO-381 không được log chứng minh**: `e2e-base-integrate-upload-x3.log` (base `8c28ef96`) đỏ 6/18 vì **chưa vẽ xong màn đầu** (`getByRole('navigation', {name:'Tải lên bản vẽ'})` hết 15 s, ×5) và `locator.fill` ô "Mật khẩu" hết 30 s (×1) — triệu chứng máy chủ dev lạnh mà chính bước làm ấm của master (`warm-dev-server.mjs`) chữa, và base chưa có bước đó. Mọi lượt base đi tới assert bộ đếm đều **xanh**; triệu chứng "1 / 4 tầng" chỉ thấy trên cây gộp (`e2e-1.log:1016-1017`, `e2e-1c…log:736-740`, 2/9 ở ×3). DEBT.md NO-381 ghi sai bằng chứng ("bộ đếm kẹt 1 / 4" trên base). NO-382 (measure) không có lượt base nào; lời phân loại dựa trên đọc mã — mã đua (`measurementToolViewModel.ts:320` `measuring: 'loading'`, `ViewerViewport.tsx:127-131` skeleton `absolute inset-0`) có nguyên trên `8c28ef96` và gộp không chạm hai tệp đó, nên hợp lý nhưng chưa đo. Gộp không chạm `src/screens/upload/**`; không chứng minh được gộp gây lỗi, cũng không chứng minh được điều ngược lại. | `backend/dieu-phoi/chay/GHEP-MASTER/e2e-base-integrate-upload-x3.log:727-860`; `DEBT.md` dòng NO-381 | Sửa dòng NO-381 cho đúng bằng chứng. X1 đo lại upload ×3 trên `8c28ef96` **có làm ấm** (hoặc sau một lượt khởi động bỏ đi) trước khi kết luận "có sẵn"; nếu base xanh thì truy nguyên trong 22 tệp master mang vào. Điều kiện merge: `pnpm e2e` 0 hỏng trên cây cuối. |
| 2 | P2 | R-07 / MNT (xung đột ngữ nghĩa bỏ sót) | Gộp giữ **hai cơ chế cùng giải một lỗi** "neo tour xuất hiện muộn": e2e/integrate `f35ce7ab` (B-V2-01) `subscribeDom` + `useSyncExternalStore` (MutationObserver trên `document.body`, subtree + thuộc tính) và master `eae963a9` (NO-208) `useEffect` + MutationObserver thứ hai + rAF + `setAnchorTick`. Mỗi lượt đổi DOM khi tour chạy phải chạy cả hai bộ dò. Không ghi trong mục "xung đột ngữ nghĩa" của `xung-dot.md` ([5] mục 3). Không sai hành vi (hai luật "sống" khớp nhau, không gây vòng render) — là mã trùng. | `src/screens/system/EditorTour/useEditorTour.ts:448-461,514-518` và `:551-593` | DEBT-03: bỏ khối `useEffect` của master (`:551-593`), giữ `subscribeDom`; cả bài NO-208 "neo có mặt SAU commit đầu" lẫn B-V2-01 phải còn xanh. Ghi dòng DEBT.md (R-34). |
| 3 | P3 | TEST | Dòng giải xung đột NO-154 (`refreshAuth` thêm tay vào lời gọi `createProgressStream` mới của F-05b) không có test nào bắt: `git grep refreshAuth` trong test chỉ ra `progressStream.test.ts`/`eventChannel.test.ts` (đơn vị của `src/lib/realtime`), không test nào của `ProcessingScreen` khẳng định cổng truyền `refreshAuth`. Xoá dòng `:826` thì cả cổng vẫn xanh. `xung-dot.md` dẫn `progressStream.test.ts` làm bằng chứng "cả hai" — test đó không chạy qua `processingGateway`. (Master cũng không có test này — không phải lùi so với master.) | `src/screens/pipeline/ProcessingScreen/processingGateway.ts:826` | DEBT-03: một test của `processingGateway` với `EventSourceImpl` giả lỗi liên tiếp ≥ `SSE_FAILURE_LIMIT` khẳng định `refreshSingleFlight` được gọi đúng một lần. Ghi dòng DEBT.md. |
| 4 | P3 | MNT (chú thích sai) | Docblock prop sau gộp nói sai mặc định: "Mặc định góc trên phải" — mặc định thật là giữa cạnh dưới (`EditorTour.tsx` `DEFAULT_CHIP_ANCHOR = 'bottom-[16px] left-1/2 -translate-x-1/2'`, test khẳng định đúng thế). | `src/screens/system/EditorTour/useEditorTour.ts:122` | Sửa chú thích thành "Mặc định giữa cạnh dưới (B-V2-05) — xem `DEFAULT_CHIP_ANCHOR`". Gộp vào DEBT-03. |
| 5 | Nit | OPS | `verify-1.log` không in sha của cây chạy; reviewer phải dựng lại bằng reflog. | `verify-1.log` | Lượt sau in `git rev-parse HEAD` + `git status --porcelain` ở đầu log. |

Không P0/P1. Không `skip/fixme` mới, không đổi `src/lib/schemas`, không nới assert, không mất test.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 3 | 0,21 |
| OBS, OPS | 5% | 4 | 0,20 |
| MNT | 3% | 3 | 0,09 |

Tổng: 4,75 / 5

## PHÁN QUYẾT: APPROVE WITH COMMENTS
Cách giải 9 tệp xung đột và các xung đột ngữ nghĩa đã ghi là đúng: giữ ý định cả hai phía, NO-154 sống trên mã F-05b, NO-209 và luồng phiên F-01b cùng giữ, nhãn A6 không nới assert, không mất test, `src/lib/schemas` không đổi, `pnpm verify` 7/7 mã thoát 0. Điểm 4,75 nhưng hạ từ APPROVE xuống APPROVE WITH COMMENTS vì tiêu chí [11.3] của prompt chưa đạt và hai P2 cần dòng DEBT.md. **Điều kiện trước khi gộp vào `master`:** (a) điều phối ghi DEBT.md cho finding 2, 3, 4 và sửa bằng chứng của NO-381 (finding 1); (b) `pnpm e2e` 0 hỏng, bỏ qua ≤ 16 trên cây cuối (sau X1/X2); (c) chuỗi thật F-14 `chuoi-1.log` xanh trên cây cuối (bước 1→11 + 8b + 10b, 0 lỗi API, 0 vi phạm CSP, 0 pageerror). Mọi commit thêm vào `merge/ghep-master` sau `81ad9154` (vá X1/X2) phải qua một lượt review đích (round-2) trước khi merge.
