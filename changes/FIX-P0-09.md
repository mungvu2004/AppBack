# FIX-P0-09 (B5-07) — bước quality ghi tóm tắt

- `apps/worker/pipeline_quality/service.py`: trong giao dịch dưới `lock_run`, **trước** `record_step(status="completed")`, gọi `record_quality_summary(db, run_id, summary=_summary(report))`.
- `_summary`: `{"hasCritical": report.has_critical, "criticalCount": số issue severity "critical", "lowConfidence": dict(report.low_confidence)}` — cùng `report` sinh `quality.json`, không đổi hình dạng `quality.json`.
- Trạng thái `completed` không đổi; lượt có lỗi nghiêm trọng vẫn `completed`. Giao lặp: `record_quality_summary` chỉ ghi khi cột NULL (trả `False` nếu đã có) — ghi đúng một lần.
- Test `apps/worker/pipeline_quality/tests/test_service.py`: `test_run_quality_records_summary_with_critical`, `test_run_quality_records_summary_clean` (so cột với `quality.json` của cùng lượt). `test_run_quality__completes_with_critical_issue_and_no_extra_notification` giữ nguyên.
- Phụ thuộc: P0-08 (cột `quality_summary`, `record_quality_summary`, `RunPins.quality_summary`).
