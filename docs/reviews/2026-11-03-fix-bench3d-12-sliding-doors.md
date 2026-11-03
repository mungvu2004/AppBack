# Review merge fix/bench3d-12-sliding-doors → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 7da998cb489b (PR #40; merge-base 297f2067ea93 = `origin/main` hiện tại, nhánh không thiếu commit nào của main; PR `MERGEABLE`)
- Cổng: Phạm vi kiểm: đầy đủ (CI GitHub Actions run 41589618366) — theo quy ước hiện hành dùng CI thay `run.sh verify`. Run 41589618366 (workflow CI, sự kiện `pull_request`, head `7da998cb489b6a20f0c076be51e8ff6c017d82d2` = đầu nhánh, `conclusion: success`): `changes`, `lint`, `typecheck`, `unit` (2 shard), `ml` (3 shard), `integration` (5 shard), `build`, `contract`, `coverage`, `perf` đều `pass`. Run 41589618445 (CodeQL, cùng SHA): `success`. Run 41589618327 (Commits, cùng SHA): `success`. Reviewer không chạy cổng hay pytest tại chỗ.
- Độ phủ (job `coverage` 125765311969 của run 41589618366, `coverage_gate: đạt`, `case_gate` 99 thao tác, 0 cảnh báo): tổng dòng 99,31% · nhánh 97,49% — gói bị chạm: `packages/domain` 99,75% / 98,60%. ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước. Nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch. 1 commit `7da998cb fix(rules-ai): wide windows into a doorless loggia become sliding doors`, đúng Conventional Commits, có `Prompt: BENCH3D-12`.
- 5 tệp, +220/−9: mã logic ~80 dòng (`post_rules.py`, `constants.py`), còn lại là test, bản tham chiếu test và `changes/BENCH3D-12.md`. Dưới 400, không cần tách.
- Có `changes/BENCH3D-12.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa`/`type: ignore` mới, không skip/xfail, không hạ ngưỡng.

## Soát nội dung

- **Gốc lỗi đúng chỗ** (`dieu-tra-r3/cua.md` §2.1): bộ dò gán `window` cho vách kính lùa ra lô gia; luật 2 cũ chỉ hạ tin cậy. Diff sửa ở luật 2 (`_fix_windows`), đúng đề xuất R1 của làn điều tra, và tinh hơn R1: thay vì chỉ ngưỡng 1400 mm, thêm điều kiện "lô gia chưa có cửa đi nối sang phòng khác", nhờ đó ngoại lệ ch-12 (cửa sổ thật 1786 mm) và syn-can-ho-4pn được giữ. Số bench: r4b không ca nào tụt hạng, O1c nhóm A Đ 23 → 28, T 4 → 2 (`KET-QUA-r4.md` §2).
- **`_sliding_door`** (`post_rules.py:221-236`): chỉ chạy trên mục `_is_target` (cửa sổ AI chưa duyệt, tường chủ chưa `envelope`) nên giữ K21; bỏ qua tường cong vì `offsetMm` đo theo cung. Bản sao đổi `kind`, `swing="sliding"`, cao 2200, bệ 0 rồi `_capped` (≤ 0,5). `door_style` của cửa sổ luôn `None` nên `model_copy` (không chạy validator) không tạo dữ liệu hỏng; `swing="sliding"` có trong `Literal`. Chỉ có QC `DOOR-WIDTH` ngưỡng dưới (`apps/api/rules/catalog.py:79`), cửa lùa 1400–3117 mm không bắn luật mới.
- **`_rooms_beside`** (`post_rules.py:194-206`): dò tại tâm ô mở, cùng tầm `thickness/2 + EXTERIOR_PROBE_MM` với `wall_side_by`. `Segment._has_length` (`spatial/model.py:187`) chặn tường dài 0 nên không chia 0. `_RoomIndex.at` trả vị trí nhỏ nhất (danh sách ô lưới chèn theo thứ tự vị trí), khớp bản tham chiếu `next(...)` quét theo thứ tự phòng; `usages` dựng từ cùng `layer.rooms`.
- **`_entered_rooms`** (`post_rules.py:209-218`): một lượt qua ô mở, mọi nguồn (cả cửa của người), tính trên lớp vào. Cửa ra ngoài (một bên không phải phòng) không tính lối vào — có test.
- **Idempotent**: lượt hai, cửa đã đổi không còn là cửa sổ; tập "đã có lối vào" chỉ lớn thêm nên cửa sổ còn lại không đổi; mọi test gọi `_apply` khẳng định `f(f(x)) == f(x)` và bằng bản tham chiếu quét toàn bộ.
- **Tương tác luật 3 trong luật 2**: cửa sổ đã đổi thành cửa đi `continue` trước khi tính `sides`, nên tường chủ chỉ mang cửa đổi không bị nâng `envelope`. Muốn đổi thì cần tâm ô mở hai bên đều là phòng — tường đó vốn là tường trong; chỉ khác khi tường dài mà trung điểm có một bên trống (xem Nit #6).
- SEC/CON/RES: hàm thuần trên mô hình miền, không đầu vào người dùng mới, không I/O, không trạng thái dùng chung. DB/API: không migration, không đổi `openapi`/hợp đồng; job `contract` xanh.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | TEST | Docstring `_rooms_beside` nêu lý do dò ở tâm ô mở ("tường dài có thể chỉ kề lô gia một đoạn") nhưng không test nào phân biệt tâm ô mở với trung điểm tường: `GLASS` (ô mở tâm 1500, trung điểm 2000) và `UNDER` (ô mở phủ cả tường) cho cùng kết quả ở hai điểm dò. Đổi điểm dò về trung điểm tường thì cả bộ test vẫn xanh. | `packages/domain/rules_ai/tests/test_sliding_door.py:15-20`, `post_rules.py:194-206` | Thêm một ca: tường `y=4000` từ x 0 tới 5500 (trên là khách + lô gia, dưới là phòng ngủ), cửa sổ 1500 tại offset 4000 → cửa đi; cửa sổ 1500 tại offset 500 (khách ↔ phòng ngủ) → giữ cửa sổ. |
| 2 | P3 | R-07 | `_rooms_beside` chép lại công thức pháp tuyến + tầm dò của `wall_side_by` (`run_x/run_y/length`, `reach = thickness/2 + EXTERIOR_PROBE_MM`, `shift = (-run_y, run_x)/length·reach`); docstring tự nói "cùng tầm với `wall_side_by`". Hai nguồn sự thật: đổi tầm dò ở một chỗ thì luật cửa lùa và phân loại tường lệch nhau. | `packages/domain/rules_ai/post_rules.py:194-206`; `packages/domain/rules_ai/geometry.py:148-156` | Tách `probe_points(wall, along_mm) -> tuple[tuple[float, float], tuple[float, float]]` trong `geometry.py`; `wall_side_by` gọi với trung điểm (cộng phần lệch cung), `_rooms_beside` gọi với tâm ô mở. Bản tham chiếu test giữ công thức riêng (đối chứng độc lập). |
| 3 | P3 | LOG | Điều kiện dựa vào `usage == "loggia"` mà nhãn này có thể là đoán (lô gia viền `from_rim`, lô gia mặt ngoài `from_facade` của BENCH3D-03), không chỉ từ chữ. Hai luật đoán chồng nhau: phòng nhỏ chưa tên trên mặt ngoài bị đoán là lô gia + cửa sổ rộng không có cửa đi bên cạnh → thành cửa đi. `Room` không có trường nguồn tên nên luật không phân biệt được. Bench r4b không ca nào tụt, rủi ro thấp. | `packages/domain/rules_ai/post_rules.py:233`; `apps/worker/pipeline_build/rooms.py:901-915` | Chấp nhận; ghi giới hạn này vào `changes/BENCH3D-12.md`. Nếu sau này `Room` mang nguồn tên, cân nhắc chỉ đổi khi lô gia có nhãn chữ hoặc tin cậy cao. |
| 4 | P3 | R-34 | Giới hạn đã biết từ điều tra không được ghi lại trong sổ nợ của prompt: lô gia không thành phòng (ch-01, ch-04, cn-01, cn-04, cn-13 — cửa kính nằm trên tường `envelope`, luật không chạm) và cửa lùa vỡ thành hai cửa sổ < 1400 mm (ch-02, cn-10; R5 chưa làm). Chỉ có trong `dieu-tra-r3/cua.md` §4 ngoài repo. | `changes/BENCH3D-12.md:1-7` | Thêm một dòng "Chưa phủ: …" liệt kê hai giới hạn trên và hướng xử lý (nhãn YOLO "cửa kính lùa", gộp mảnh R5). |
| 5 | Nit | PERF | `_entered_rooms` dò hai điểm cho mọi cửa đi kể cả khi tầng không có lô gia nào. Chi phí nhỏ (một lượt O(số cửa), tra lưới). | `packages/domain/rules_ai/post_rules.py:252` | Có thể bỏ qua khi `"loggia" not in usages`; không bắt buộc. |
| 6 | Nit | DOC | Trước đây cửa sổ trên tường mà trung điểm có một bên trống làm tường được nâng `envelope`; nay nếu cửa sổ đó đổi thành cửa lùa (tâm ô mở hai bên là phòng) thì tường không còn được nâng ở luật 2. Đúng ý (tường đó là tường trong ở đoạn có cửa) nhưng docstring `_fix_windows` không nói. | `packages/domain/rules_ai/post_rules.py:239-248` | Khi chạm lại, thêm một câu vào docstring. |
| 7 | Nit | LOG | Hai lô gia nối nhau bằng cửa đi nhưng không lô gia nào nối vào trong nhà thì cả hai đều tính "đã có lối vào", ô kính rộng giữ cửa sổ. Hiếm, không có ca bench. | `packages/domain/rules_ai/post_rules.py:209-218` | Không cần đổi. |

Không có P0/P1/P2. Không nợ nào tác giả nêu mà thiếu ghi; #4 là giới hạn từ tài liệu điều tra nên ghi thêm.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,84 / 5

## PHÁN QUYẾT: APPROVE

Sửa đúng gốc chung đã điều tra (luật 2 chỉ hạ tin cậy cửa kính lùa bị dò thành cửa sổ) bằng một luật tổng quát có điều kiện chặt: cửa sổ AI chưa duyệt, tường thẳng, rộng ≥ 1400 mm, hai bên đều là phòng, một bên là lô gia chưa có lối vào. Tín hiệu "chưa có lối vào" giữ được cửa sổ thật (ch-12, syn-can-ho-4pn) thay vì nâng ngưỡng. K21 giữ nguyên, idempotent và khớp bản tham chiếu được khẳng định ở mọi test, không đổi API/DB/hợp đồng FE. CI GitHub Actions trên đúng SHA đầu nhánh xanh toàn bộ, độ phủ `packages/domain` và tổng ≥ 90/90. Bốn P3 và ba Nit làm ở lượt sau (ưu tiên #1: test phân biệt tâm ô mở với trung điểm tường; #4: ghi giới hạn vào `changes/BENCH3D-12.md`).
