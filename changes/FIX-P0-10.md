# FIX-P0-10 — N16 trả `readiness` của tầng (B3-02)

- `apps/api/spatial_read/readiness.py` (mới, worker-safe): `readiness_of(*, run, scale_source, layer) -> ReadinessOut` thuần + `latest_run_facts(db, floor_pk)` — một truy vấn: lượt `completed`, `superseded_by IS NULL` mới nhất của tầng, join trái `pipeline_run_models` (`pinned`, `quality_summary`).
- Luật (H5 §2.2): `scaleUnresolved` ⇔ `scale_status(nguồn đã chấm hạng theo trang) == "unresolved"`; `criticalIssues` ⇔ `quality_summary.hasCritical is True`; `fallback{Wall,Object,Text}Model` ⇔ `pinned[wallSegmentation|openingAndFurnitureDetection|dimensionReading]` là ref cổ điển (`ModelRef.is_classic`). Lý do cấp lượt tắt khi `level_reviewed(...)`. Không có lượt → `notEvaluated` (vẫn kèm `scaleUnresolved` nếu có); có lượt, không lý do → `ready`; còn lại `needsReview`.
- `wire.py`: `ReadinessOut`, `FloorLayerDocumentOut.readiness` (luôn có). `router.py` nối dây; `assemble.py` không đổi.
- Test: `tests/test_readiness.py` (bảng 15 ca + hạ hạng `human` khi đổi trang); `test_routes_layer.py` thêm `__C01_readiness_needs_review|ready|not_evaluated` (golden tự ghi); `test_wire.py`, `test_boundary.py` cập nhật.
- Cần điều phối: tái sinh `openapi.json`; FE FIX-P0-02 (`readiness` trong `spatialLayer.ts`) phải vào trước khi nâng `APPFRONT_SHA` cho bước 7.
