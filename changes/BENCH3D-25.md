# BENCH3D-25 — tường thẳng bị chẻ nhiều khúc khác bề dày; góc L hở làm mất phòng khách

- Mới `pipeline_build/wall_runs.py` `merge_wall_runs`, gọi trong `build._attempt` sau `apply_post_rules` (đã có `kind`),
  trước `settle_reversed`: khúc AI chưa duyệt, thẳng, cùng `kind`, thẳng hàng (≤ 2°, lệch tim ≤ ½ bề dày) và chạm/chồng
  nhau (khe ≤ 10 mm) → một tường (id + tim của khúc dài nhất), bề dày = trung vị theo độ dài của `detectedThicknessMm`,
  bắt bậc một lần; ô mở đặt lại `offsetMm` (khúc ngược chiều: đổi `left`/`right`); `room.wallIds`, `dimension.referenceIds`
  đổi theo id gộp. Cùng `kind` giữ tường bao 220 tách vách 100 nối thẳng qua chữ T.
- `pipeline_build/rooms.py` `_corner_closers` (cuối `_gap_closers`, cho đầu tự do chưa được khép): góc L hở — đầu tự do và
  đầu tường vuông góc đều cách giao điểm hai tim ≤ 1,5 x bề dày lớn hơn, giao điểm không giữa thân tường kia → đoạn khép tới
  giao điểm, không xét hướng ra. Đoạn đi vào `closers_out` như mọi đoạn khép (`close_envelope_gaps` dựng tường vỏ).
- `pipeline_quality/checks.py` `ROOMS_WITHOUT_DOOR`: cửa tính cho phòng khi tường cửa trong `wallIds` **và** tâm cửa cách
  biên phòng ≤ bề dày tường — tường dài đã gộp chạy qua nhiều phòng không còn cho mọi phòng "có cửa".
- `packages/vision/dimensions/rooms.py`: tên phòng không rõ `phòng khác` → `phòng chưa rõ tên` (AppFront `registry.ts`
  nhánh `feat/wall-review-ux` đã đổi); tên cũ vẫn không đọc lại thành nhãn.
- Không đổi API/DB/OpenAPI/hợp đồng. Không đổi vector hoá (bước ML): gộp ở bước dựng phủ mọi nguồn khúc.
- Đo (replay bench-3d trên đầu ra ML đã lưu, cùng mã ngoài nhánh; `F:/runs/bench-3d/dot5/`): cặp tường AI thẳng hàng chạm
  nhau 710 → 96 (khác bậc 500 → 69; tầng có cặp 84 → 47/95; còn lại 95 % là khác `kind`). bench 66: ĐẠT 39 → 39
  (+syn-can-ho-150 W6, −ch-10 P5 6,7 → 10,2 % vì bề dày trung vị), im lặng 8 → 7. Tập F 29 (giữ riêng, không chỉnh ngưỡng
  trên nó): ĐẠT 8 → 8, f-22 có lại phòng khách 30 m² (W1, O1, O1c, O5, P3 lên), f-02/f-11 W4, f-13 S4 lên, f-06 P6 Đ → C;
  f-17 thành im lặng: cờ cũ `ROOMS_WITHOUT_DOOR` là cờ nhầm (cửa chính nằm trên tường qua khe không thuộc `wallIds`) che
  lỗi dò cửa O1c có sẵn. bench-can-ho 14: phòng không đổi (riêng 78, gộp 24, thiếu 7, công năng 75), cặp 45 → 8.
- Vector hoá (đề xuất nới `_PIECE_THICKNESS_RATIO`, `_cluster_lines`) không làm: bước ML, phải vá f14-ml và vector hoá lại
  bench; gộp ở bước dựng đã thu cặp chạm nhau, tim khúc lệch được đặt về tim khúc dài nhất.
- Vòng sửa sau merge-review (`docs/reviews/2026-11-04-fix-wall-runs-lcorner.md`): P1 perf — tìm cặp ứng viên lọc theo lô
  (hộp bao + cùng hướng + cùng `kind` bằng numpy) trước vòng Python: `merge_wall_runs` trên ca perf 20 000 tường 0,26 →
  0,10 s CPU; `_corner_closers` không đo được khác nhiễu (ca perf không có góc hở) nên giữ truy vấn từng cặp. P3: nhóm lệch
  khỏi tim khúc dài nhất (chuỗi cặp lệch dần) và nhóm có ô mở đặt lại chồng nhau/lố tường → giữ nguyên các khúc.
- Nợ chấp nhận (P2 review): chạy lại pipeline trên tầng dựng **trước** nhánh này mà người dùng đã duyệt/xoá một khúc lẻ:
  `rules_ai.merge._same_run` khớp theo hai đầu mút nên tường gộp không khớp khúc đã duyệt/bia mộ → tường AI dài chồng tường
  đã duyệt, khúc đã xoá hiện lại trong tường gộp. Sửa đúng phải cắt tường AI quanh khúc giữ/bia mộ trong `merge.py`, mà
  `merge.py` không được sinh id mới (K18) — cần prompt riêng (cắt + id tất định). Tầng dựng sau nhánh khớp bình thường
  (tường gộp được duyệt/xoá nguyên khối). Nợ còn lại (P3): tâm cửa trên tường cong đo trên dây cung (`checks._door_centres`);
  khi chạy lại, kích thước AI cùng trỏ một tường gộp bị coi trùng kích thước người đã giữ (`rules_ai/dimensions.py`).
