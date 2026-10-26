# Review merge fix/apt-title-block → main (lượt 2 của fix/apt-scale-chains) + AppFront fix/error-resource-sharelink

- Ngày: 2026-10-27 · Reviewer: phiên /merge-review · Commit đầu nhánh: 5be55028 (base `main` 95d3c78a); AppFront `fix/error-resource-sharelink` d75d1d56 (trên `origin/master` b41fa8f5)
- Nguồn luật: `RULE.md`, `RULE-CODE.md`, `DEBT.md` không có trong repo; dùng `docs/charter/*` và tiền lệ `docs/reviews/*`.
- Cổng: phạm vi **đầy đủ**. Lượt 2 nhưng diff có mã mới (FIX-2450 sửa route công khai, FIX-2451 tiền xử lý) và chạm `APPFRONT_SHA`. Reviewer tự chạy `bash tools/verify/run.sh verify` tại 5be55028, f14 dừng trong lúc chạy: mã thoát **0** (log `F:/worktrees/AppBack/apt-sheet-verify-r2.log`). Bước 0–8 đạt cả mười; 8883 passed; 5b perf 9 test + `case_gate` đạt; bước 7 H1 2134 mẫu, AppFront @ d75d1d56.
- Độ phủ (`coverage_gate`): tổng dòng 99,49% · nhánh 98,02%; tập file bị chạm 99,07% / 94,39%. `apps/api/share_links` 100/90, `apps/ml/text` 98,39/96,43, `apps/worker/pipeline_build` 99,09/95,45, `apps/worker/pipeline_orchestrate` 98,67/97,06, `packages/vision` 99,65/98,45, `tools` 98,76/96,50.

## Phạm vi và điều kiện dừng sớm

- Cây sạch. 14 commit trên `origin/main` (3 merge nội bộ giữa `fix/apt-scale-chains`, `fix/main-gate`, `fix/apt-title-block`), đều `Prompt: SB-APT-SCALE` + `Fix: FIX-2449..2452`. 27 file, +1255/−34.
- **Dừng sớm §2, không đạt:** `f8e73e84` chạm `docs/charter/BE-BIND.md` **cùng** `.py` (`test_routes_read.py`, `tools/tests/test_charter.py`, `tools/contract/tests/test_check.py`) và `tools/contract/schema-map.ts`, và **không** có trailer `Charter-Approved:`. Thân commit có ghi "BE-BIND edit approved by the project owner" nhưng không trỏ tới bản duyệt nào. Luật skill: chạm `docs/charter/*` thì commit chỉ chạm tài liệu và mang trailer trỏ bản duyệt có thật, thiếu một là REJECT. Tiền lệ: `2026-10-06-fix-fix-378-pascal-flag-compose-round-2.md` (REJECT cùng lý do), `7c23d018` (commit charter đúng mẫu: chỉ tài liệu, `Charter-Approved: người dùng duyệt 2026-10-12 ("duyệt charter 27")`).
- **Dừng sớm §2, không đạt:** không có `changes/FIX-2450.md` (5 route mới gắn hợp đồng, 3 lỗi sản phẩm sửa ở route công khai `GET /api/share/{token}`) và `changes/FIX-2452.md` (ghim lại `APPFRONT_SHA`). FIX-2449 và FIX-2451 có tệp `changes/`.
- `tools/contract/APPFRONT_SHA` (`5be55028`): tệp cấm ở §2, **chấp nhận**: do điều phối commit, giống tiền lệ `2026-10-13-refactor-f-15-pascal-flag.md:12`. Điều kiện: d75d1d56 hiện **chỉ có ở nhánh local** của AppFront, nên phải lên `origin` trước khi `main` của AppBack trỏ tới nó (xem finding 5).
- Không có `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới, không hạ ngưỡng; không chạm `uv.lock`, `pyproject.toml`, `openapi.json`.

## Lượt 1 đã đóng (26df1be1)

| Finding lượt 1 | Trạng thái |
|---|---|
| 1 P3 `np.pad` cả trang mỗi chữ | đóng: `_near` dựng một lần mỗi chiều trong `dimension_spans` |
| 2 P3 float64 cả ảnh | đóng: số nguyên `uint32`, `+500 // 1000` làm tròn |
| 3 P3 hoà cụm là đoán (K19) | đóng: hai cụm đông nhất rời nhau → `()`; cụm hoà chồng nhau → tâm nhỏ nhất; có test cả hai ca |
| 4 P3 ghi chú triển khai cùng SHA | đóng: `changes/FIX-2449.md` |
| 5 Nit số đo trong `changes` | đóng |
| 6 Nit chữ một ký tự | chấp nhận (không sửa) |
| 7 Nit kiểm `span_px` hai lần | đóng |
| Cổng đỏ do `main` | đóng: `f8e73e84` thêm dòng BE-BIND #47–49, N39, N40 và snapshot C01 `edited`; bước 5 và 7 xanh |

## Reviewer tự kiểm

1. **FIX-2451 trên 14 ảnh bench.** Chạy `find_frame` + `drawing_quad` của nhánh lên `F:/runs/bench-can-ho/raw/*` (script `<scratchpad>/sheet_probe.py`, ảnh `appback-ml:f14`, mã mount từ worktree). 6 ảnh CAD (ch-01..06) bị cắt cột khung tên ở x ≈ 1050–1071 cùng viền. 5 ảnh không phải CAD cũng bị cắt mép dưới: ch-07 10 px, ch-09 9 px, ch-10 17 px, ch-11 55 px (và 3 px quanh viền), ch-12 10 px. ch-08, ch-13, ch-14 giữ nguyên. Không ảnh nào mất phần mặt bằng: đường cắt nằm ngoài `plan_bbox_px` của đáp án ở cả 5 ca.
2. **So `run2` → `run4` của bench** (`layer.json`): ca CAD bớt phòng giả (ch-02 16 → 9/9, ch-03 15 → 7/7, ch-04 12 → 7/7), nhưng ch-01 12 → 6/7, ch-05 12 → 5/7, ch-06 8 → 4/6 phòng. Một ca không phải CAD tụt: ch-07 Σ diện tích 56,3 → 26,8 m² (đúng ≈ 69 m²), dù chỉ bị cắt 10 px mép dưới, ngoài mặt bằng. `KET-QUA.md` đã ghi đây là độ nhạy của model tường khi ảnh lệch, nhưng `changes/FIX-2451.md` không ghi (finding 3). ch-10 72 → 116 m².
3. **Ca cắt nhầm dựng tay** (`<scratchpad>/sheet_fp.py`). Mặt bằng 1000×800 cắt sát mép, tường đen 10 px: tường bao, một vách dọc chạy suốt ở x = 760, cột phòng bên phải có 3 tường ngang. `drawing_box` → `(27, 27, 757, 771)`: cả cột phòng x 760–980 (22 % mặt bằng) bị coi là khung tên và cắt bỏ, tường bao bị coi là nét viền và cắt qua giữa. Xem finding 1.
4. **FIX-2450 route công khai.** `reject_foreign_origin` và `rate_limit(key_ip, store="cache", on_error="open")` theo đúng mẫu các route khác (`auth/router.py:121`, `drawings/router.py:40`). Redis cache được `flushdb` mỗi test (`packages/testing/fixtures/messaging.py:148`), nên C11 không rò hạn mức sang test khác. FE mở `/api/share/{token}` bằng GET cùng origin, không gửi `Origin`, nên C24 không chặn người xem thật. `NfcStr` cho `label`, `viewpoint_code` đúng K20.
5. **AppFront d75d1d56.** Thêm `'shareLink'` vào `ERROR_RESOURCES` (tuple không export; không có `switch` vét cạn theo nó). Bằng chứng chạy là bước 7 của cổng trên, ghim d75d1d56: H1 đạt 2134 mẫu, gồm các mẫu `NOT_FOUND resource=shareLink` trước đó làm H1 đỏ (`verify-apt-sheet-2.log` của tác giả). Reviewer không chạy `pnpm verify` của AppFront cho thay đổi một dòng này; CI của AppFront chạy khi push.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| A | **§2 REJECT** | BE-00 §2 / merge-review §2 | `f8e73e84` sửa `docs/charter/BE-BIND.md` cùng `.py` và `tools/**`, không có `Charter-Approved:` | `f8e73e84` | Nhánh chưa lên `origin`, nên viết lại lịch sử được. Tách `f8e73e84` thành: (1) `fix(contract): …` gồm `schema-map.ts`, 3 file test; (2) `docs(charter): BE-BIND #47–49, N39, N40 …` **chỉ** `BE-BIND.md`, trailer `Charter-Approved: người dùng duyệt 2026-10-26 ("<câu duyệt>")` hoặc đường tệp duyệt (như `7c23d018`). Cây cuối giữ nguyên thì cổng này dùng lại được. |
| B | **§2 REJECT** | BE-00 §13.2 | Thiếu `changes/FIX-2450.md` và `changes/FIX-2452.md` | `changes/` | FIX-2450: 5 route gắn hợp đồng (dòng BE-BIND, `schema-map`, `cases.toml`), C16/C11/C24 của share link (đỏ trước, nay xanh), hạn mức 60/phút/IP fail-open, snapshot C01. FIX-2452: ghim AppFront d75d1d56, lý do H1 `shareLink`, phải push AppFront trước. Chỉ tài liệu. |
| 1 | P2 | LOG-01 / R-19 | `drawing_box` nhận **mọi** nét đậm chạy suốt làm vạch ngăn, ô bảng hay viền, kể cả tường. Ảnh mặt bằng cắt sát (ảnh web, đường auto không có góc người dùng) có vách dọc chạy suốt ở 65–97 % bề rộng và ≥ 3 tường ngang bên phải sẽ mất cả cột phòng; tường bao trong 4 % sát mép bị cắt qua giữa. Tái hiện ở "tự kiểm" 3. Bench không có ca này, nhưng cắt im lặng mặt bằng là mất dữ liệu, người dùng chỉ sửa được bằng góc tay. | `packages/vision/preprocess/sheet.py:60-110` (`_full_lines`, `_title_divider`, `_border_inset`) | Chỉ nhận nét **mảnh**: nhóm cột liền nhau của `_full_lines` rộng ≤ `max(3, 0,004 · cạnh)` px (nét khung CAD 1–2 px trên ảnh gốc; tường ≥ 5 px), áp cho vạch ngăn, đường ô và nét viền. Thêm test từ ca tái hiện (khẳng định `drawing_box(...) is None`). Nếu không sửa: ghi dòng nợ P2 có chủ trong mục "Nợ" của `changes/FIX-2451.md`. |
| 2 | P3 | TEST-01 | Test của `drawing_box` chỉ có một ca âm cho tường (`strip_without_cells_is_not_a_title_block`, vùng phải không có ô). Không có ca "cột phòng có tường ngang" hay "tường bao sát mép" | `packages/vision/preprocess/tests/test_sheet.py:49` | Gộp vào finding 1. |
| 3 | P3 | OPS / R-02 | `changes/FIX-2451.md` không ghi rằng ảnh không phải CAD cũng bị cắt mép (ch-07/09/10/11/12, 9–55 px), cũng không ghi ch-07 tụt Σ diện tích 56 → 27 m², ch-01/05/06 mất phòng thật (6/7, 5/7, 4/6) | `changes/FIX-2451.md` | Thêm 2 dòng: số phòng/diện tích `run2` → `run4` của cả 14 ca, và việc kế "độ nhạy model tường khi ảnh lệch" (đã có trong `KET-QUA.md`). |
| 4 | P3 | TEST (AppFront) | Không có test dương cho `resource: 'shareLink'`; tên test `từ chối resource ngoài mười lăm giá trị` nay sai, vì đã có 16 giá trị | AppFront `src/api/__tests__/contracts/errors.test.ts:96` | Thêm `it('nhận resource shareLink', …)`; đổi "mười lăm" → "mười sáu". Có thể làm ở vòng sau, không chặn. |
| 5 | P3 | OPS | `APPFRONT_SHA` = d75d1d56 chỉ có trên nhánh local `fix/error-resource-sharelink`, `origin/master` = b41fa8f5. Đẩy `main` của AppBack trước thì CI và `web-context.sh` không lấy được SHA ghim | `tools/contract/APPFRONT_SHA` | Thứ tự gộp: AppFront `fix/error-resource-sharelink` → `master` (fast-forward, d75d1d56 giữ nguyên SHA) rồi push, rồi mới gộp và push AppBack. |
| 6 | Nit | MNT | `_full_lines` tính `_longest_runs` cho cả ảnh rồi mới lọc `[low, high)` | `packages/vision/preprocess/sheet.py:58-60` | Cắt `ink[:, low:high]` trước. Không bắt buộc (+1,4 s ở 40 MP theo tác giả). |

Đã soát, không có finding: SEC (route công khai thêm chặn `Origin` và hạn mức; không biên vào mới; `NfcStr` ở biên), CON (không trạng thái chung mới; hạn mức qua script Redis nguyên tử có sẵn), RES (fail-open có chủ ý cho trang chỉ đọc, ghi trong docstring), DB/API (không migration; openapi đạt; hợp đồng FE H1–H5 đạt), `rectify` → `crop` (kẹp vào ảnh; homography tịnh tiến; chỉ khi lọt `max_pixels`; khung lệch > 2 px vẫn nắn; có test), `drawing_quad` đưa góc về ảnh gốc qua nghịch đảo homography (có test khung lệch 1 px).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3,5 | 0,525 |
| PERF | 10% | 4,5 | 0,45 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 4,5 | 0,315 |
| OBS, OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4 | 0,12 |

Tổng: **4,61 / 5** · P0: 0 · P1: 0 · P2: 1 · P3: 4 · Nit: 1 · §2 dừng sớm: 2

## PHÁN QUYẾT: REJECT

Lý do là thủ tục (§2), không phải mã. Mã và cổng đạt mức APPROVE: cổng đầy đủ tại 5be55028 thoát 0 ở cả 10 bước, độ phủ ≥ 90/90 ở mọi gói chạm, mọi finding lượt 1 đã đóng, không P0/P1, điểm 4,61. Để được APPROVE ở lượt 3:
1. **A:** tách `f8e73e84` để `BE-BIND.md` nằm trong một commit chỉ tài liệu, trailer `Charter-Approved:` trỏ tới lời duyệt có thật của người dùng.
2. **B:** thêm `changes/FIX-2450.md` và `changes/FIX-2452.md`.
3. **Finding 1 (P2):** sửa theo đề xuất kèm test, hoặc ghi dòng nợ P2 có chủ trong `changes/FIX-2451.md`. Finding 3 (tài liệu) nên làm cùng.
4. Lượt 3 phạm vi **đích**: nếu cây chỉ khác 5be55028 ở `changes/*.md` (A, B, finding 3), `git diff 5be55028 <mới> --stat` chỉ ra tài liệu → dùng lại cổng này. Nếu sửa finding 1 trong mã → `verify --steps 1,2,3,4` + pytest/coverage `packages/vision/preprocess`.
5. Khi APPROVE: gộp AppFront `fix/error-resource-sharelink` vào `master` và push **trước**, rồi mới gộp AppBack (finding 5).
