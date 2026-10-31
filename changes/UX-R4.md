# UX-R4 — sửa sau đợt kịch bản UX R3

## bc — U57: bỏ nét sơ đồ vị trí căn (key plan) ở brochure

- `apps/worker/pipeline_build/geometry.py` `_drop_far_clusters` (bước 3, sau `_drop_isolated`): gom cụm tường liên thông
  (tim cách ≤ nửa tổng bề dày + `WALL_JOIN_MM`); vùng chính = hộp cụm dài nhất, nới dần bằng mọi cụm có hộp cách vùng
  ≤ 1,5 m (vách bị khe cửa cắt rời, ban công/lô gia, cột sát căn). Cụm còn lại có tổng dài < 15 % mọi tường **và** hộp
  < 10 % hộp vùng chính thì bỏ, đếm vào `dropped.isolatedBlock`, log `pipeline_build_far_cluster_dropped`.
  Ngưỡng ở `constants.py` (`FAR_CLUSTER_*`).
- Đo 14 ca `F:/runs/walls-tidy/cases` (bảng ở `F:/runs/r4-bc/KET-QUA.txt`): chỉ ch-07 (32 → 30) và ch-08 brochure
  (31 → 30, tường giữa ô 15/14 của key plan) giảm; 12 ca còn lại giữ nguyên danh sách tường, không thêm xiên/không chuẩn.
- Không đổi API, DB, migration, hợp đồng FE–BE (khoá `dropped` giữ nguyên 12).
- Test: `apps/worker/pipeline_build/tests/test_geometry_walls.py` (key plan xa bị bỏ, vách trong + ban công 1 m giữ;
  cụm xa cỡ lớn giữ). Chạy chọn lọc 71 test pipeline_build + ruff + mypy thư mục: đạt. Cổng đầy đủ: chưa chạy.
