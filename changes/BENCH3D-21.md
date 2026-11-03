# BENCH3D-21 — tỉ lệ ước: chữ diện tích căn, giường, hai trục chuỗi

- `apps/worker/pipeline_build/build.py`: nhánh ước lượng (dự án chưa đặt tỉ lệ) thêm ước giường (`_bed_scale`, cạnh dài 2066 mm, trung bình nhân với cửa khi lệch ≤ 25 %) và tỉ lệ từ chữ diện tích căn (`_area_note_scale`, gốc mới `areaNote`: giá trị ≥ 20 m² ngoài phòng, chặn tờ nhiều căn/dải diện tích/chữ phòng lớn, độ phủ phòng ≥ 0,75 bao lồi tường, 0,8–1,35× ước cửa); lớp đổi tỉ lệ bằng `rescale_unreviewed`.
- `_resolved_scale`: cụm chuỗi chung hoà rỗng mà cụm chữ ngang và chữ dọc đều suy được, lệch ≤ 15 % → trung bình nhân hai trục (gốc `chain`, `scaleChecks.anisotropic` vẫn ghi nên vẫn báo `scaleUnresolved`).
- `areaNote` vẫn là ước lượng: không vào `_MEASURED_BASES`, readiness vẫn báo `scaleUnresolved`.
- Hợp đồng: `ScaleBasis` (wire + `docs/contracts/openapi.json`) thêm `areaNote`. FE không đọc `scaleBasis`. Không migration.
