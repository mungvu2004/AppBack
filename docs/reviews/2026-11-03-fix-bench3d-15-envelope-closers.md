# Review merge fix/bench3d-15-envelope-closers → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: dfbd958688da (PR #43; merge-base 297f2067ea93 = `origin/main` hiện tại, nhánh không tụt sau main; PR `MERGEABLE`)
- Cổng: Phạm vi kiểm: đầy đủ (CI GitHub Actions run 41589650803) — quy ước hiện hành dùng CI thay `run.sh verify`. Run 41589650803 (workflow CI, `pull_request`, head `dfbd958688dac1f993afadf2484ddb6e6793d9c5` = đầu nhánh): `changes`, `lint`, `typecheck`, `unit` (2 shard), `ml` (3 shard), `integration` (5 shard), `perf`, `build`, `contract`, `coverage` đều `success`. Run 41589650720 (CodeQL, cùng SHA): `success`. Run 41589650732 (Commits, cùng SHA): `success`. Reviewer không chạy cổng hay pytest tại chỗ.
- Độ phủ (job `coverage` của run 41589650803, `coverage_gate: đạt`, `case_gate` 99 thao tác, 0 cảnh báo): tổng dòng 99,30% · nhánh 97,52% — gói bị chạm: `apps/worker/pipeline_build` 98,33% / 93,73%. Đều ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước. Nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch (`.bench3d/` bị bỏ qua). 4 commit, dòng đầu đúng Conventional Commits, mỗi commit có `Prompt: BENCH3D-15`:
  `d013ea1e fix(pipeline-build): wall the exterior room closers into the envelope`,
  `5642823f test(pipeline-build): widen courtyard case past envelope gap limit`,
  `0397ed30 fix(pipeline-build): match envelope duplicates by kind and alignment`,
  `dfbd9586 fix(pipeline-build): wall the closer shoulders beside a bridged opening`.
- 7 tệp, +633/−67; mã logic ~233 dòng thêm (`geometry.py` +255/−55, `rooms.py` +21/−6, `build.py` +11/−3), còn lại là test và `changes/BENCH3D-15.md` — dưới 400, không cần tách.
- Có `changes/BENCH3D-15.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa` trần, `type: ignore`, skip/xfail mới, không hạ ngưỡng.
- Đúng làn L4 của `BRIEF-dot3.md`: `close_envelope_gaps` + helper trong `geometry.py`, `rooms.py` chỉ trả closers ra (`_door_closers` kèm nhãn, tham số tuỳ chọn `closers_out` — chữ ký cũ vẫn gọi được), `build.py` chỉ chỗ nối. `origin/fix/bench3d-16-room-outline` (L5, PR #44) đã chứa sẵn `closers_out`/`RoomCloser` của nhánh này và xuất thêm cạnh đường bao (`_open_edge_closers`) — tức phát hiện #3 của Codex r3 được xử lý ở L5, không thuộc PR này. **Thứ tự gộp: #43 trước #44.**

## Soát nội dung

- **Đoạn khép → tường vỏ** (`geometry.py:1398-1467`): chỉ dựng khi `_inner_room` thấy đúng một bên là phòng (cùng phép dò `wall_side_by` của luật 2, nhớ phòng phía trong); khe trong nhà và khe sân trong (không bên nào là phòng) giữ hở — có test cho cả hai. Đoạn chồng/cắt tường đang có, kể cả tường vừa thêm, vẫn bỏ qua bằng `_clash` (W4); đoạn góc trùng khe với đoạn hộp bị bỏ nhờ thứ tự `_door_closers` trước `_gap_closers` (test `window_box_on_gap_becomes_window_wall`).
- **Hành vi cũ của `bridges`** giữ nguyên: vẫn đòi `hosts` và không cắt tim tường nào; khe ngắn vẫn `_extend_host`; khe dài vẫn cửa đi đoán — trừ R2' (phòng trong `loggia`/`utility`/`other` → tường đặc). Hai test cũ của `test_geometry_openings.py` phải gán `usage="bedroom"` mới giữ được cửa đoán (xem finding #1).
- **Chọn ô mở** (`_gap_target`, `geometry.py:1265-1281`): hộp có nhãn → ô mở cùng loại tin 0,5; không hộp → cửa sổ tin 0,3 khi `_glazed` thấy ≥ 2 nét liền và dải mực ≤ 60 % bề dày; còn lại tường đặc, không đoán cửa đi. `_glazed` chặn trang lệch khổ mặt nạ, hàng tràn mép trang; ba trường hợp nét kính/khối đặc/trống có test. Giới hạn đã đánh dấu `ponytail:` (tường hai nét mà mặt nạ bỏ sót cũng ra 2 nét).
- **Trùng hộp** (`_opening_near`, `geometry.py:1325-1350`): sửa đúng Codex r3 #4 — đòi cùng loại, tường chủ song song cách đường khe ≤ 300 mm, khoảng chiếu giao khe; ba ca của Codex có test (cửa sổ vuông góc gần góc, cửa sổ thẳng hàng khác loại, cửa đi thẳng hàng). Còn ca "chỉ chạm" (finding #2).
- **Vai hai bên ô mở 3c** (`_uncovered`, `geometry.py:1356-1395`): gốc lấy từ `debug-closers.md` (7/7 `skip_clash` ở ch-09/cn-01/cn-06/cn-07 đều là tường `NOINPUT` mang một ô mở chồng song song lên closer cả khe). Trừ phần tường song song đã phủ, phần còn ≥ 100 mm thành khe riêng nhãn `None`; đoạn cắt xuyên tường trả nguyên để vòng chính bỏ như cũ (test `closer_crossing_a_wall_still_skipped`). Đây là sửa gốc ở chỗ mọi đoạn khép đi qua, không vá từng ca.
- **`RoomCloser`**: dataclass đóng băng, đơn vị mm, `js_round` hai đầu; `rooms.py` import từ `geometry.py` vốn đã import trước đó, không tạo vòng.
- SEC/CON/RES: không đầu vào người dùng mới, không I/O, không trạng thái dùng chung. DB/API: không đổi schema `layer.json`, không migration, job `contract` xanh; lớp dựng ra chỉ thêm tường/ô mở `source="ai"`, `reviewed=False`, tin ≤ 0,5.
- PERF: mỗi khe một lượt quét tường (`_uncovered`, `_clash`, `_opening_near` dựng `by_id` mỗi lần) — O(khe × tường), vài chục × vài trăm; job `perf` xanh.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG | R2' tắt cửa đoán khi phòng trong là `other`, nhưng `other` cũng là tên dự phòng của mọi phòng không đọc được nhãn (`name_rooms`: `None` → `other`, `packages/vision/dimensions/rooms.py:231`). Tầng không có chữ (OCR hỏng, bản vẽ không ghi tên) thì mọi phòng là `other` → C5 không bao giờ đoán cửa đi nữa: cửa chính bộ dò bỏ sót thành tường đặc, căn hộ không lối vào. Chính hai test cũ (`test_geometry_openings.py:865`, `:977`) phải ép `usage="bedroom"` để giữ cửa đoán. Lý do R2' trong `cua.md` là "lan can" của lô gia, không phải phòng chưa tên. | `apps/worker/pipeline_build/geometry.py:100`, `:1274-1275` | Chỉ tính `other` khi tầng có ≥ 1 nhãn chữ (như luật lô gia `labelled_level` của BENCH3D-03), hoặc bỏ `other` khỏi `_NO_GUESSED_DOOR`; thêm test tầng không chữ giữ cửa đoán. Tối thiểu ghi giới hạn này vào `changes/BENCH3D-15.md`. |
| 2 | P3 | LOG | `_opening_near` coi khoảng chiếu **chạm** khe là trùng (`along[1] >= 0 and along[0] <= span`), test còn khẳng định (`aligned-door-touching-gap`: cửa đi y 2000–2900 trên tường phải chặn hộp cửa đi y 1000–2000). Hai ô mở cùng loại kề nhau (hai cửa sổ liền, hai cửa đi cạnh nhau) thì đoạn khép của hộp thứ hai bị bỏ hẳn (`continue`, không cả tường đặc) — vỏ chỉ kín nếu tình cờ có đoạn góc trùng khe. | `apps/worker/pipeline_build/geometry.py:1347`; `tests/test_envelope_closers.py:241` | Đòi giao dương, ví dụ `min(along[1], span) - max(along[0], 0) > _OVERLAP_MIN_MM`; đổi ca test thành "chồng" và thêm ca "chỉ chạm → vẫn dựng cửa". |
| 3 | P3 | TEST | Số đo bench (W1 nhóm A Đ 23→29, `KET-QUA-r4.md`) đo trên `integ/bench3d-r4` gộp cả L2–L5, không tách được phần của nhánh này; gốc "vai" chỉ có trong `debug-closers.md` ngoài repo. Test chỉ dựng lưới tổng hợp (test `closer_skips_part_under_bridged_wall` tái hiện đúng dạng cn-01/cn-06). Ba seed e2e (105, 108, 109) mất cửa chính đoán theo R2' được ghi nhận bằng cách đổi khẳng định, không có đối chiếu đáp án. | `changes/BENCH3D-15.md`; `apps/worker/pipeline_build/tests/test_e2e_real.py:26-27`, `:125` | Chấp nhận (luật heuristic, có số đo). Ghi vào `changes/BENCH3D-15.md` một dòng: số W1 là của bản gộp; seed 105/108/109 đổi cửa chính đoán → tường đặc là hệ quả R2' có chủ đích. |
| 4 | Nit | DOC | Docstring test còn tiêu chí cũ "tâm ≤ nửa khe + 300 mm" đã bị `0397ed30` thay bằng cùng loại + song song + khoảng chiếu. | `apps/worker/pipeline_build/tests/test_envelope_closers.py:101` | Sửa câu docstring theo tiêu chí mới. |
| 5 | Nit | DOC | Commit `dfbd9586` và `changes/BENCH3D-15.md` nói phần "vai" còn hở thành "tường đặc"; thực tế phần ≥ 600 mm đi qua `_gap_target` nên có nét kính thì thành cửa sổ tin 0,3 (hợp lý khi hộp 3c ngắn hơn cửa sổ thật). | `apps/worker/pipeline_build/geometry.py:1455-1457`; `changes/BENCH3D-15.md:5` | Sửa câu trong `changes/BENCH3D-15.md`: "tường đặc, hoặc cửa sổ nếu có nét kính". |
| 6 | Nit | MNT | `wall_side_by` lấy từ mô-đun con `packages.domain.rules_ai.geometry`, không qua `__all__` của gói như `outline_contains` ở dòng ngay trên. Không vi phạm `lint-imports` (CI xanh). | `apps/worker/pipeline_build/geometry.py:40-41` | Khi chạm lại: xuất `wall_side_by` trong `packages/domain/rules_ai/__init__.py` (việc của chủ gói), import một chỗ. |

Không có P0/P1/P2. Không nợ P0/P1 mở.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,76 / 5

## PHÁN QUYẾT: APPROVE

Sửa đúng gốc W1 đã chứng minh trên f14: đoạn khép phòng giờ thành tường vỏ ở mặt ngoài, phần "vai" cạnh tường qua khe 3c được trừ đúng chỗ thay vì bỏ cả đoạn, và phép chống trùng hộp đã sửa theo Codex r3 #4. Khe trong nhà/sân trong giữ hở, chồng/cắt tường vẫn bỏ, hành vi cũ của `bridges` giữ nguyên ngoài R2'; mỗi nhánh mới có test. Không đổi API/DB/hợp đồng FE. CI GitHub Actions trên đúng SHA đầu nhánh xanh toàn bộ, độ phủ gói bị chạm và tổng ≥ 90/90. Không P0/P1/P2; ba P3 và ba Nit làm ở lượt sau — ưu tiên #1 (R2' với phòng chưa tên trên tầng không chữ) và #2 (chạm ≠ trùng). Gộp #43 trước #44 (L5 xây trên `closers_out` của nhánh này).
