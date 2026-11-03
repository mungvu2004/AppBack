# BENCH3D-21 — tỉ lệ chuỗi khi hai trục ảnh giãn khác nhau (T3)

- `apps/worker/pipeline_build/build.py` `_resolved_scale`: cụm chuỗi chung hoà rỗng (hai cụm rời cùng cỡ) mà cụm chữ ngang và cụm chữ dọc đều suy được, lệch ≤ 15 % → tỉ lệ = trung bình nhân hai trục, gốc `chain` (f-23: +12,3 % → −1,6 %). Lệch hơn (1:100 cạnh 1:50) → không đoán như cũ.
- Tỉ lệ cứu bằng T3 luôn ghi `scaleChecks.anisotropic` (kể cả hai trục lệch < 3 %) nên readiness vẫn báo `scaleUnresolved` — không thêm tỉ lệ "đã giải" mới.
- `_axis_clusters` tách từ `_anisotropy` (dùng chung). Không đổi hợp đồng/openapi, không migration.
- T1 (diện tích căn + giường) ở nhánh riêng `fix/bench3d-21-scale-t1`, không gộp: replay làm xấu cn-04/cn-11/cn-22.
