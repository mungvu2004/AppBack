# FIX-P0-08 — lưu tóm tắt bước quality theo lượt (B5-06a)

- Cột mới `pipeline_run_models.quality_summary JSONB NULL` (`packages/db/models/pipeline_orchestrate.py`); revision `r20261026_b5_06a_p0_08` (`packages/db/migrations/versions/r20261026_b5_06a_p0_08_quality_summary.py`), down `r20261025_share_links`, expand thuần, `downgrade()` xoá cột.
- `apps/worker/pipeline_orchestrate/pins.py`: `record_quality_summary(db, *, run_id, summary) -> bool` ghi một lần (`UPDATE … WHERE quality_summary IS NULL`), không có dòng hay đã ghi → `False`; `RunPins.quality_summary` (mặc định `None`), `load_pins` đọc cột.
- Factory `make_run_pins(..., quality_summary=...)`.
- Test `test_pins.py`: `test_record_quality_summary_writes_once`, `…_returns_false_without_row`, `test_load_pins_quality_summary_none_before_quality_step`; mở rộng `test_make_run_pins_applies_used_and_persisted_revision`.
- Lượt cũ `NULL` = không có lý do `criticalIssues` (FIX-P0-10). Người ghi là bước quality (FIX-P0-09).
