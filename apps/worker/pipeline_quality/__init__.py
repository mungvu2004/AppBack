"""Kiểm chất lượng một lượt pipeline (`qualityCheck`, bước cuối, B5-07).

Task `pipeline.quality.run` (`tasks`) kiểm toàn vẹn lớp đã ghi, đếm mục AI tin cậy thấp, ghi artifact
`quality.json` rồi đẩy bước cuối qua `record_step` (lượt `completed`). Hàm worker khác nhập thẳng
module con (`report`, `service`); `celery_main` nạp `tasks` qua `discover_submodules`.
"""
