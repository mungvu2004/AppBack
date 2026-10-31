# UX-R4 — đợt sửa UX vòng 4 (AppBack/AI)

## bb — U34: sửa nhãn đồ theo kích thước thật

- `apps/worker/pipeline_build/rooms.py`: `relabel_by_size` chạy trong `build_furniture`, đo hộp ở tỉ lệ `final` (mm):
  `chair`/`other` cỡ giường (ngắn 900-2000, dài 1900-2200) → `kind="bed"`, trừ khi tâm nằm trong phòng khách, bếp,
  WC, hành lang, lô gia (bộ sofa + bàn trà cũng cỡ giường); `chair` dài ≥ 1400, ngắn 600-1100 → `kind="chair"` +
  `variant="sofa"`. Hợp đồng `Furniture.kind` không có sofa nên dùng `variant` có sẵn (thư viện xếp sofa vào nhóm ghế).
- Tỉ lệ chưa tin (`project_default` hay ước từ bề dày tường): vẫn đổi, `confidence` hạ về `LOW_CONFIDENCE_CAP`.
- Bàn, tủ bếp và các nhãn khác không đụng. Đo 14 ca bench: 12 món ghế → sofa, 0 giường; bảng `F:/runs/r4-bb/KET-QUA.txt`.
- Lệch: FE vẫn ghi chữ theo `kind` ("Ghế") cho sofa; đổi chữ cần FE đọc `variant`.

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

## bd — nối đầu tường lơ lửng (bước 10e)

- `packages/vision/walls/vectorize.py`: bước 10e `_bridge_dangling_ends` sau 10c/10d, trước `_rotate`. Đầu tường
  ngang/dọc không chạm tường nào, nhìn thẳng ra trước gặp tường khác hở mặt-tới-mặt ≤ 1,5 × bề dày lớn → kéo tới
  tim (tường vuông góc) hoặc đầu mút gần (tường thẳng hàng, bề dày lệch ≤ 1,25 lần); tường gặp đầu tiên thắng nên
  không kéo xuyên tường; góc L hở thì kéo nốt tường kia. Chưa có thông tin cửa ở bước này nên khe dài hơn để lại.
- Đo 14 ca (`F:/runs/r4-bd/KET-QUA.txt`): ch-09 đầu lơ lửng 13 → 10; ca khác không đổi; số cửa, phòng, xiên,
  không chuẩn không ca nào xấu đi. ch-04 chưa đỡ: khe 470–1090 mm theo phương tường cần biết cửa (bước sau).
- Test: `packages/vision/walls/tests/test_bridge_ends.py`.
