"""Ghi kết quả pipeline vào tài liệu tầng (`spatialDataBuild`, B5-06b).

Task `pipeline.persist.run` (`tasks`) đọc `layer.json` của B5-05, trộn lớp AI vào tài liệu tầng
qua `write_layer(merge=…)`, chụp phiên bản trước/sau, đẩy bước, báo `aiCompleted`, gửi
`pipeline.quality.run`. Hàm worker khác nhập thẳng module con (`service`, `merge`, `context`);
`celery_main` nạp `tasks` qua `discover_submodules`, nên gói không nhập lại gì ở đây.
"""
