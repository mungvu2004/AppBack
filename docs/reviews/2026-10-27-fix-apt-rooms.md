# Review merge fix/apt-rooms → main (+ AppFront feat/room-usage-loggia)

- Ngày: 2026-10-27 · Reviewer: phiên /merge-review · Commit đầu nhánh: 3c3701b8 (base `main` 4c512903); AppFront 0c58554a (trên `origin/master` 945f12e2)
- Cổng: phạm vi **đầy đủ** (lượt 1). Reviewer tự chạy `bash tools/verify/run.sh verify` tại 3c3701b8, f14 dừng trong lúc chạy: mã thoát **0**, cả 10 bước đạt (log `F:/worktrees/AppBack/apt-rooms-verify.log`). 8925 passed; 5b perf 8 test + `case_gate` đạt; bước 7 với AppFront @ aa84d2e5, H1 3124 mẫu.
- Độ phủ (`coverage_gate`): tổng dòng 99,48% · nhánh 98,00%; tập file bị chạm 99,14% / 94,27%; `apps/worker/pipeline_build` 98,86/94,30; `packages/vision` 99,72/98,81.
- AppFront (reviewer tự chạy ở worktree `usage-loggia` @ 0c58554a): `pnpm typecheck` đạt (app + Pascal); vitest 44 file test đổi/liên quan, 581 passed; `useScaleCalibration.test.ts` cả file có coverage 50/50 (14-A-026); `eslint --max-warnings 0` trên mọi file `.ts/.tsx` đổi: sạch. Bước size: xem "Nợ có sẵn".

## Phạm vi và điều kiện dừng sớm

- Cây sạch. 5 commit, đều `Prompt: SB-APT-ROOMS`, `Fix: FIX-2453` / `FIX-2454`; có `changes/FIX-2453.md`, `changes/FIX-2454.md`. 20 file, +484/−53, mã logic ~250 dòng.
- Không có `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới; không chạm `docs/charter/*`, `uv.lock`, `pyproject.toml`, migration.
- `docs/contracts/openapi.json` và `tools/contract/APPFRONT_SHA` (`967b651f`): tệp cấm ở §2, **chấp nhận**: do điều phối commit (tiền lệ `2026-10-13-refactor-f-15-pascal-flag.md:12`, `2026-10-27-fix-apt-title-block-round-3.md`). Diff openapi chỉ có `loggia` ×3 và docstring route share (FIX-2450) chưa từng dựng lại; bước 8 đạt. aa84d2e5 là tổ tiên của 0c58554a, gộp AppFront trước thì tới được từ `origin/master`.

## Reviewer tự kiểm

1. **Khớp tên gần đúng với chữ không phải tên phòng.** `match_room_label` của nhánh (ảnh `appback-ml:f14`, mã mount từ worktree, script `<scratchpad>/label_probe.py`) trên 47 chữ hay gặp trên bản vẽ:
   - đúng `None`: "BẢN VẼ", "MẶT BẰNG TẦNG 5", "TỈ LỆ 1/100", "GHI CHÚ", "TIM TƯỜNG", "THÔNG THỦY", "DIỆN TÍCH", "BẮC", "BÀN", "KHU VỰC", "CHỦ ĐẦU TƯ", "HỘP KỸ THUẬT", "THÔNG GIÓ", …;
   - **nhận nhầm**: "SINH HOẠT" → `corridor` (đúng là `livingRoom`), "NGƯỜI VẼ" → `bedroom`, "MASTER PLAN" → `bedroom`, "NGUỒN", "NGUỒN ĐIỆN", "NGỮ" → `bedroom`, "KHÁCH HÀNG", "KHÁC" → `livingRoom`, "BÊN", "CỬA BÊN", "BẾN" → `kitchen`, "SINH" → `corridor`. Xem finding 1.
   - Dương tính đúng: "PN1", "WC02", "Phòng khách + Bếp", "LÔ GIA", "LOGOA", "PHONG NCU", "TEN SANH", "BAN CÔNG", "TIỀN SẢNH".
2. **AppFront bước size là nợ có sẵn.** `node scripts/check-bundle-size.mjs` trên bản dựng `err-sharelink` @ 44db79f3 (cây = `origin/master` 945f12e2) và `usage-loggia` @ 0c58554a đều thoát 1: cùng 46 chỗ `Function(...)` trong `pdfkit.standalone` (CSP), cùng ngân sách Pascal (tài sản 22275,6 KiB, tổng 37761,3 → 37761,6 KiB, +0,3 KiB do enum). Nhánh không làm xấu thêm.
3. **14-A-026.** `createNotificationBus` giữ `Date.now` lúc import; đổi thành `() => Date.now()`. Có test hồi quy trong `undoTicket.test.ts`. Cả file `useScaleCalibration.test.ts` có coverage: 50/50.
4. **Hợp đồng `loggia`.** Cột `usage` không phải enum Postgres nên không cần migration. Domain, dây đọc, mẫu, danh mục luật (27 khoá) và FE (zod, `Record<RoomUsage, …>` vét cạn nên `tsc` bắt chỗ thiếu) khớp; H4 và `test_fe_has_25_rules_and_27_thresholds` đạt ở bước 7.
5. **Hiệu năng.** Bước 5b đạt (`build_layer` ở trần K18: tác giả báo 33 s → 7 s sau `3c3701b8`). `_seeded_outlines`, `_room_labels`, `_fixture_labels` tra bằng `STRtree`; `match_room_label` có `lru_cache`, `RoomLabel` là `frozen` nên dùng chung kết quả nhớ đệm an toàn.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG-01 | Khớp gần đúng nhận nhầm chữ thường gặp, xem "tự kiểm" 1. Gốc lỗi: luật khoá 3 chữ `token[:3] == key` nhận mọi chữ **bắt đầu** bằng "ngu"/"bep" ("nguon", "nguoi"); "sanh" sai 1 khớp "sinh"; "khach" khớp "khac"; khoá nhiều chữ "master" nhận "master plan". Tác động: (a) tên/công năng sai cho phòng chứa chữ đó ("SINH HOẠT" là nhãn phòng khách phổ biến, thành hành lang); (b) chữ khớp nhầm nằm **ngoài** mọi phòng khép sẽ mọc phòng hộp ≤ 40 m² (`_seeded_outlines` dùng chung `parsed`), ví dụ "NGUỒN ĐIỆN", "NGƯỜI VẼ" khi khung tên không bị cắt. Phòng AI có `reviewed=false` và sửa được ở RoomLabelReview, nên là P2 chứ không phải P1. Bench báo sai công năng tăng 2 → 13 (đúng tăng 11 → 66). | `packages/vision/dimensions/rooms.py:113-160` (`_near`, `_fuzzy_usage`); `apps/worker/pipeline_build/rooms.py:156-209` | (1) Luật tiền tố 3 chữ chỉ khi `len(token) <= 4` ("ngui" vẫn khớp, "nguon"/"nguoi" thì không); (2) bỏ khớp gần đúng "sanh" ↔ chữ có nguyên âm khác ở vị trí 2 (hay bỏ "sanh" khỏi `_FUZZY_WORDS`: "TEN SANH" vẫn qua bước 2); (3) "khach" chỉ khớp chữ ≥ 5 ký tự; (4) **phòng mọc từ nhãn chỉ dùng nhãn khớp nguyên khoá**, không dùng nhãn khớp gần đúng; (5) "sinh hoat" thêm vào khoá `livingRoom`; (6) đưa 47 chữ của "tự kiểm" 1 vào bảng tham số test. Theo luật nợ giữa đợt, việc này vào đợt sửa kế. |
| 2 | P3 | OPS / DB-02 | `loggia` mở rộng enum trên dây đọc. FE cũ đọc đồ thị có phòng `loggia` sẽ hỏng ở zod, nên ảnh `web` phải lên cùng `api`/`worker`. Lùi BE về ảnh trước khi đã lưu phòng `loggia` thì `Room` (Literal) không đọc được tài liệu không gian đó. `changes/FIX-2453.md` không ghi thứ tự triển khai và rủi ro lùi bản. | `changes/FIX-2453.md` | Thêm: "Triển khai `web` (AppFront ≥ aa84d2e5) cùng lượt `api`/`worker`; sau khi có phòng `loggia` thì không lùi BE về trước FIX-2453." |
| 3 | Nit | LOG | `_seeded_outlines`: tâm chữ nằm đúng trên một đường khép thì một tia có độ dài 0, hộp suy biến, rồi bị đếm `roomTooSmall` (nhiễu bộ đếm, không sai hình). | `apps/worker/pipeline_build/rooms.py:190-200` | Bỏ qua khi `min(reach) == 0`. |

**Nợ có sẵn, không phải finding của nhánh:** AppFront `pnpm size` hỏng trên `master` (46 chỗ dựng mã từ chuỗi trong `pdfkit.standalone`; ngân sách màn đầu, CSS, Pascal), xem "tự kiểm" 2. CI AppFront trên `master` hỏng sau 3–4 s ở mọi lần push gần đây (`gh run list`: 40376708233, 40312468564, …), nghĩa là chưa có job nào chạy thật. Hai việc này vào sổ nợ đợt kế.

Đã soát, không có finding: SEC (không biên vào mới; chữ OCR chỉ ánh xạ về tên chuẩn `ROOM_USAGE_NAMES`, không chép chữ OCR, BE-00 §10), CON (hàm thuần; `lru_cache` trên hàm thuần, kết quả bất biến), RES (không I/O mới), `_fixture_labels` (ngưỡng có test âm/dương: tủ ngắn, phòng > 10 m², tủ áo ở phòng 32 m²), `_room_labels` ưu tiên công năng chính (có test "tiền sảnh + phòng khách"), `ROOM_GAP_CLOSE_MM` 1200 (có lý do và số bench trong docstring), AppFront `loggia` (fitout cấm giường/tủ/bếp/vệ sinh, không cần cửa/cửa sổ, nhóm màu `circulation`).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3,5 | 0,525 |
| PERF | 10% | 4,5 | 0,45 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4,5 | 0,315 |
| OBS, OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4,5 | 0,135 |

Tổng: **4,58 / 5** · P0: 0 · P1: 0 · P2: 1 · P3: 1 · Nit: 1

## PHÁN QUYẾT: APPROVE

Cổng đầy đủ AppBack thoát 0 ở cả 10 bước, độ phủ ≥ 90/90 ở mọi gói chạm. AppFront: typecheck, eslint và vitest các file đổi đạt; bước size hỏng y hệt trên `master`. Không P0/P1, điểm 4,58 ≥ 4,0. Bench đo trên f14 cải thiện lớn (đúng công năng 11 → 66, thiếu phòng 28 → 12). Finding 1 (P2, khớp gần đúng nhận nhầm) và finding 2 (P3, ghi chú triển khai) vào đợt sửa kế, có chủ là phiên điều phối. Thứ tự gộp: AppFront `feat/room-usage-loggia` → `master`, push; rồi `fix/apt-rooms` → `main`, push.
