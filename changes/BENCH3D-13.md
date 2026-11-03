# BENCH3D-13 — tỉ lệ: ảnh giãn không đều, ghi chú TL trên PDF ảnh, mẩu tường lạc

- `pipeline_build/build.py`: `scaleChecks.anisotropic` (chữ ngang/dọc lệch > 3 %) và gốc `chain` → tỉ lệ là trung bình nhân hai trục thay cụm đông nhất (một trục), chỉ khi hộp chữ hai cụm trục cắt nhau (chuỗi bao cùng một căn); cụm rời nhau (mặt bằng 1:100 + chi tiết 1:50) giữ cụm đông nhất, chỉ ghi nghi vấn. `scaleMillimetresPerPixel` vẫn một số; khoá nghi vấn giữ nguyên.
- `build_layer(vector_page=...)`: PDF chỉ chứa ảnh (không `preprocess/vectors.json`) → ghi chú `TL 1:N` chỉ nhận khi lệch ước cửa đi ≤ 10 % (`_trusted_note`), không thì về ước lượng như chưa có ghi chú. `pipeline_build/tasks.py` `stat` khoá `vectors.json` của lượt (chỉ khi có `px_per_paper_mm`).
- `pipeline_build/geometry.py` `_drop_far_clusters`: thêm luật mẩu lạc — cụm tổng dài < min(600 mm, 3 % tổng) mà hộp lòi khỏi hộp cụm dài nhất quá bề dày lớn nhất → bỏ (`isolatedBlock`), kể cả khi nằm trong `FAR_CLUSTER_GAP_MM`; trong dải 1 m quanh hộp chỉ bỏ khi nằm trên đường gióng của tường cụm chính (trụ ban công song song vỏ được giữ).
- Không đổi hợp đồng API/openapi, không migration.
