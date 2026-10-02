"""Runner huấn luyện (B6-03b): task `ml.training.runner.start` khởi chạy tiến trình con `run_training_job`.

Luật vòng đời ở BE-00 §7 "Tiến trình huấn luyện"; nghĩa vụ trainer ở BE-00 §9. Không nhập
`packages.db`, `apps.api`, `apps.worker`; gặp cầu nối B6-03a chỉ qua payload B5-01 và mẫu khoá.
"""
