"""Đánh giá một bản model trên tập kiểm tổng hợp cố định (B6-04b): task `ml.infer.ml_eval.evaluate_version`.

Đo bản gốc seed, bản tải lên và bản vừa huấn luyện bằng đúng một số đo của họ
(`FAMILY_METRIC`), gửi kết quả cho cầu nối B6-03a (`evaluation_done` → `set_evaluation`
của B6-01). Bản trên storage là model người dùng: chỉ nạp trong hộp cát (`sandbox`).
Nhập gói không nhập `ultralytics`, `torch`.
"""
