# FIX-IT-DIAGONAL-OPENINGS — gộp khe cửa trên bản vẽ chéo, kẹp ô mở trên tường ngắn (BUG-IT-007/009)

- `apps/worker/pipeline_build/geometry.py` 3b: cặp tường mà **cả hai** lệch trục > `DIAGONAL_ALIGN_DEG=5` (constants.py)
  dùng sai số 5° cho `_aligned`/`_perpendicular` thay vì 2°; lệch ngang đo giữa hai đầu mút gần nhau vuông góc với
  hướng trung bình (≤ ½ bề dày). Tường thẳng trục giữ nguyên 2° và phép đo hai đầu của `b` (B5-05 [6] 3b).
- Bước 4 `_candidate`: rộng mặc định > chiều dài tường mà tường ≥ `OPENING_MIN_WIDTH_MM=300` → kẹp về chiều dài;
  tường < 300 vẫn `openingTooWide`. Chồng nhau sau khi kẹp vẫn qua `openingOverlap`.
- Phát lại G2..G5 (artifact lượt mới nhất): cửa đi giữ 5/12/20/15 → 5/13/21/23, cửa sổ 5/18/13/30 → 5/18/13/31;
  G5 đoạn nối (bridges) 13 → 23.
- Test: `apps/worker/pipeline_build/tests/test_geometry_openings.py`; `degenerate_projection_falls_back_too_wide` viết lại
  thành `degenerate_projection_clamped_to_short_wall` (tường 800 nay giữ cửa 800), nhánh rơi chuyển sang
  `wall_under_min_width_too_wide`. Không đổi API, migration, hợp đồng FE.
- Review 2 P2: trần `offsetMm` dùng `floor(L - rộng)` để ô mở kẹp không lố đầu tường chéo (test tường 476,6 mm).
