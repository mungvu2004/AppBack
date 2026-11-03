# Review merge fix/bench3d-05-room-recognition → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 7c2b1eefcc8f (PR #35, `MERGEABLE`; merge-base = `origin/main` 08947af4e21d, nhánh không đi sau main)
- Cổng: phạm vi đầy đủ (CI GitHub Actions run 41558927655). Người dùng quyết định dùng CI thay `run.sh verify` vì máy đang chạy lượt chụp 3D. Run 41558927655 (workflow CI, head `7c2b1eefcc8f961ee63448f2c1b7937b82104ac3` = đầu nhánh) kết luận `success`, mọi job `success`: `changes`, `lint`, `typecheck`, `unit` (2 shard), `ml` (3 shard), `integration` (5 shard), `perf`, `build`, `contract`, `coverage`. Run 41558927653 (CodeQL, cùng SHA): `success`. Run 41558927656 (Commits): `success`. Reviewer không chạy cổng hay pytest tại chỗ.
- Độ phủ (job `coverage` 125666281336, `tools.coverage_gate`: đạt; `tools.case_gate`: đạt, 0 cảnh báo): tổng dòng 99,31% · nhánh 97,50%. Gói bị chạm: `apps/worker/pipeline_build` 98,27% / 93,36%. Đều ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết bench-3d trước. Nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch, nhánh đã đẩy (`origin/fix/bench3d-05-room-recognition` = HEAD). Một commit `7c2b1eef fix(pipeline_build): name open-plan living rooms and facade loggias`, đúng Conventional Commits, có `Prompt: BENCH3D-05`.
- 3 tệp, +165/−12: `rooms.py` +78/−12 (logic ~60 dòng), test +91, `changes/BENCH3D-05.md` mới. Dưới 400 dòng.
- Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Diff không có pragma, `noqa`, `type: ignore`, skip/xfail, không hạ ngưỡng.

## Soát nội dung

- **Phòng khách không gian mở** (`_open_space_labels`, `rooms.py:608-622`, gọi ở `:906`): tầng chưa có `livingRoom` thì mọi phòng "bếp"/"hành lang" > 18 m² thành phòng khách; không có thì phòng chưa tên lớn nhất > 18 m² khi tầng có ≥ 1 phòng có tên. Chạy sau cùng, trên cả nhãn chữ lẫn nhãn suy.
- **Lô gia tầng không ghi chữ** (`rooms.py:883-894`): `read_level = labelled_level or any(from_fixtures)`; nhánh mới: 2–15 m², không giường/thiết bị vệ sinh, `max(facade, exposed) ≥ 3 m`, cạnh ngắn hộp bao xoay ≤ 2 m. `_exposed_lengths` dùng `STRtree` + `dwithin` 2·`ROOM_SNAP_MM` (300 mm). Biên phòng nằm trên tim tường (docstring `_FACADE_MM`), nên hai phòng kề chung cạnh, không phụ thuộc bề dày tường: dung sai 300 mm đứng được. `_depth_mm` chỉ chạy khi các điều kiện trước đã đúng (`and` lười).
- **Nguồn tên**: `sources` nay tính từ `merged`, nên phòng chưa tên được đổi thành phòng khách có nguồn `inferred` (test `rooms[1].confidence < 1.0`).
- **Test**: 4 test mới phủ phòng hẹp/sâu, lô gia lõm khỏi biên bao lồi, bếp/sảnh rộng có/không phòng khách, phòng chưa tên lớn nhất. Test cũ `test_short_cabinet_with_dining_set_names_kitchen_not_bedroom` đổi kỳ vọng `kitchen` → `livingRoom`, đã nêu trong `changes/BENCH3D-05.md`. Dùng `fake_clock`, không thời gian thật.
- SEC/CON/RES/DB/API: không đầu vào mới, không I/O, không trạng thái dùng chung, không đổi API/DB/hợp đồng FE (job `contract` xanh).

### Overfitting: các ngưỡng mới có đứng được ngoài bench không

- `_OPEN_SPACE_M2 = 18`: có lý do miền ngoài bench (bếp riêng căn hộ VN thường ≤ 15 m²). Các ca bench nằm ở 24–52 m², cách ngưỡng xa, nên không phải số chỉnh khít theo bench. **Đứng được với bếp.** Với "hành lang"/"sảnh" thì chỉ có **một mẫu** (ch-11, 27 m²) và không có điều kiện hình dạng. Hành lang chung của mặt bằng tầng điển hình nhiều căn (đã nằm trong phạm vi đa tầng) thường > 18 m², nên luật này dễ đổi nó thành "phòng khách" (finding #3).
- `_LOGGIA_DEPTH_MM = 2000`: lô gia/ban công căn hộ VN thường sâu 1,2–1,8 m; bench 0,99–1,91 m. 2 m là cận trên chung, không khít theo ca. **Đứng được.**
- `_exposed_lengths`: là một ý hình học chung (cạnh không giáp phòng nào), không gắn với ca cụ thể. **Đứng được**, nhưng thiếu ca âm (finding #4).
- Bằng chứng định lượng chỉ là mô phỏng trên chính layer r2, tức cũng là nơi chọn ngưỡng ("không ca có đáp án nào giảm"). Chưa có tập giữ lại (finding #5).
- Không thấy ngưỡng riêng cho từng ca hay tên ca nào trong mã. Tên ca chỉ xuất hiện trong docstring để dẫn nguồn.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG / OBS (B12) | `_open_space_labels` ghi đè cả **nhãn chữ OCR**: phòng có chữ "BẾP", "PHÒNG ĂN" (`phong an` → kitchen), "SẢNH", "TIỀN SẢNH", "HÀNH LANG" > 18 m² thành "phòng khách". `sources` vẫn là `"text"` vì `from_text[i]` khác `None` (`:909`), nên `room_confidence` cho `_NAME_TRUST["text"] = 1.0` với một tên do heuristic đặt, trái chữ trên bản vẽ. Phòng như thế không bị đẩy sang hàng duyệt tin cậy thấp. Test `test_wide_kitchen_or_hall_is_the_living_room_unless_the_level_has_one` (`test_rooms.py:921-922`) xác nhận sảnh có chữ thành `livingRoom` nhưng không kiểm tin cậy. | `apps/worker/pipeline_build/rooms.py:616`, `:906-910` | Khi `merged[i] != from_text[i]` thì nguồn là `"inferred"`, ví dụ `"text" if text and text == label else "inferred" if label else "none"`. Thêm assert `confidence < 1.0` cho ca "SANH". |
| 2 | P2 | LOG | Nhánh dự phòng dùng `any(named)` để coi tầng là "đã đọc được" (docstring `_OPEN_SPACE_M2`: "của tầng đã đọc được"). Nhưng `named` gồm cả lô gia rìa (`from_rim`) và hộp kỹ thuật (`from_shaft`), hai nhãn chỉ suy từ hình học. Tầng mà OCR và dò đồ đạc đều hỏng (YOLO không ra cửa nào, nên mọi phòng < 2,5 m² đều là "hộp kỹ thuật", xem finding #1 của review BENCH3D-03) vẫn đổi phòng chưa tên lớn nhất thành phòng khách. Đây đúng là kiểu "đoán mù" mà `read_level` ở `:883` được thêm vào để chặn. Test `test_bed_in_a_merged_region_over_25_m2_is_not_a_bedroom` chỉ xanh vì lưới của nó không có phòng nhỏ hay rìa nào. | `apps/worker/pipeline_build/rooms.py:618` | Truyền `read_level` vào `_open_space_labels` và dùng nó thay `any(named)`. Thêm test: tầng không chữ, không đồ đạc, có một ô < 2,5 m² và một phòng 20 m² → vẫn "phòng khác". |
| 3 | P2 | LOG (overfit) | "hành lang"/"sảnh" > 18 m² → phòng khách dựa trên **một** ca bench (ch-11), không điều kiện hình dạng. Hành lang chung của tầng điển hình nhiều căn, hay hành lang dài ở nhà phố/biệt thự, dễ vượt 18 m² mà vẫn hẹp. Tầng không có chữ "phòng khách" nào thì hành lang ấy thành "phòng khách", kết hợp #1 còn mang tin cậy 1,0. Bếp thì có lý do miền (≤ 15 m²); hành lang thì không. | `apps/worker/pipeline_build/rooms.py:616` | Chỉ đổi "corridor" khi phòng không hẹp, ví dụ `_depth_mm(outline) > _LOGGIA_DEPTH_MM` hay một ngưỡng sâu ~2,5 m có lý do miền (hành lang ≤ 1,2–2 m). Thêm test: hành lang 1,5 × 14 m = 21 m² giữ "hành lang". Không làm được thì ghi rủi ro vào `changes/BENCH3D-05.md`. |
| 4 | P3 | TEST / DOC | Nhánh lô gia hẹp + `exposed` chạy cho mọi `read_level`, **gồm cả tầng có nhãn chữ** (`read_level = labelled_level or …`). Docstring `_FACADE_MM` và `changes/BENCH3D-05.md` lại nói đây là nhánh cho tầng chỉ có tên suy từ đồ đạc. `exposed` tính so với các phòng **đã giữ**, nên phòng chưa tên hẹp (hành lang, kho) giáp ô thang/giếng trời không khép thành phòng cũng được tính "lộ" ≥ 3 m và thành lô gia. Không test âm nào cho ca này. | `apps/worker/pipeline_build/rooms.py:118-124`, `:883`, `:890` | Sửa docstring/changes cho khớp mã (hoặc giới hạn nhánh như mô tả). Thêm test âm: hành lang 1,2 × 5 m giữa nhà, một cạnh dài giáp vùng hở không khép → không phải lô gia. |
| 5 | P3 | TEST (overfit) | Kết quả "P4 tăng 12 ca, không ca nào giảm" là mô phỏng trên chính layer r2, nơi chọn ngưỡng. Chưa có số trên tập giữ lại. Bài học `wall-refine-rules-overfit` cho thấy luật hậu xử lý từng +0,06 trên tập chọn và −0,06 trên tập giữ lại. | `changes/BENCH3D-05.md:5` | Chấm trước/sau trên một tập không dùng để chọn ngưỡng (vd `F:/runs/bench-can-ho`, 14 bản) và ghi số vào `changes/BENCH3D-05.md`. Không chặn merge. |
| 6 | Nit | MNT | Docstring `_open_space_labels` vượt một dòng tóm tắt (PEP 257: dòng đầu đứng riêng). | `apps/worker/pipeline_build/rooms.py:609-610` | Khi chạm lại, tách dòng tóm tắt. |

Không P0/P1. Ba P2 đều sửa được ở chỗ gốc bằng vài dòng. Rủi ro tác giả tự nêu (cn-19 kho 3,8 m² thành lô gia) đã có trong `changes/BENCH3D-05.md`.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3 | 0,45 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,57 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1, điểm 4,57 ≥ 4,0, CI GitHub Actions trên đúng SHA đầu nhánh xanh toàn bộ, độ phủ gói bị chạm và tổng ≥ 90/90. Ngưỡng 18 m² cho bếp và 2 m cho độ sâu lô gia có lý do miền ngoài bench và cách xa dải giá trị của bench, nên không phải chỉnh khít từng ca. Điểm yếu nằm ở việc áp luật rộng hơn bằng chứng: ghi đè nhãn chữ mà vẫn giữ tin cậy 1,0 (#1), coi tầng chỉ có nhãn hình học là "đã đọc được" (#2), và hành lang rộng → phòng khách chỉ dựa trên một mẫu (#3). Nên sửa ba P2 này trước khi merge, mỗi cái vài dòng kèm một test. Nếu merge ngay thì ba dòng nợ phải vào `changes/BENCH3D-05.md` cùng lúc merge.
