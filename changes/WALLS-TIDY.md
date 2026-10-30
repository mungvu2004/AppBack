# WALLS-TIDY — dọn tường vụn sau vector hoá

- `packages/vision/walls/vectorize.py` bước 10c `_straighten_jogs`: bản vẽ vuông góc, tường — đoạn chéo — tường song song lệch ≤ 1,5 bề dày (ô kỹ thuật áp tường) → một đường thẳng, bỏ đoạn chéo, góc L ở đầu kia dời theo.
- Bước 10d `_merge_line_pieces` (chạy trước và sau 10c): khúc ngang/dọc cùng đường chạm/chồng nhau, bề dày lệch ≤ 1,25 lần → một tường; khúc mảnh nằm trọn trong khúc khác bỏ; cột dày trên vách và khe cửa giữ riêng.
- `apps/worker/pipeline_build/geometry.py` `_absorb`: nối hai tường qua khe cửa lấy bề dày tường dài hơn (trước lấy lớn hơn: vách 2,8 m dày 100 thành 200 vì mẩu cột 0,5 m bên kia khe); tường chồng nhau vẫn lấy lớn hơn.
- Đo trên 14 bản vẽ mẫu + H-02 (mask f14): H-02 35 → 31 tường, 1 → 0 tường xiên; không bản nào thêm tường xiên/không chuẩn; bề dày đổi ở ch-01/02/09 khớp nét mực hơn (105–112 mm thay vì 143–159).
- Không đổi API, DB, migration, hợp đồng FE–BE.
- Cổng áp dụng: lint/type, test packages/vision/walls, apps/worker/pipeline_build. Migration/hợp đồng: không áp dụng.
- `apps/worker/pipeline_steps/tests/test_sweep_rules.py`: hai test quét bù chỉ đọc thông điệp ML của đúng lượt đã dựng. Cổng đầy đủ 31/10 hỏng 1/9243 vì `EvaluateVersionPayload` từ test quản trị mô hình tới muộn trên hàng ML (chạy riêng: 17/17 đạt).
- Nợ NO-430 (mở): test `admin_ml_registry` gửi `EvaluateVersionPayload` sau commit mà không chờ/dọn, thông điệp rò sang test sau trong cùng tiến trình. Sửa: chờ dispatch sau commit xong (hoặc dọn hàng) ngay trong test gửi.
