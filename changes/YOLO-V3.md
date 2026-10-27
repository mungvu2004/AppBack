# YOLO-V3 — ngưỡng hiển thị bàn/ghế/giường cho model đồ rời

- Chỉ đổi `LABEL_CONFIDENCE_MIN` (apps/ml/objects/detector.py): bed 0,8, chair 0,5, table 0,6.
- Nguồn số: quét P/R của yolo11m-v3 trên validation CubiCasa với đáp án đồ rời (F:/App/docs/yolo-do-roi/cham-v3-final.md).
- Không đổi API, DB, migration, hợp đồng FE–BE. Model v3 kích hoạt qua registry (N26/N24), không nằm trong repo.
- Cổng áp dụng: lint/type, test apps/ml/objects. Migration/hợp đồng: không áp dụng.
