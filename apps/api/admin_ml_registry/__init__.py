"""Registry model ML: N23-N27, lịch đánh giá lại, dọn object mồ côi (B6-01).

Module sở hữu hai bảng `model_families`, `model_versions` và là **nguồn duy nhất** để
worker biết bản nào đang kích hoạt cho mỗi họ: `registry.py` phơi các hàm ấy cho
`apps/worker` và `apps/ml` (BE-00 §7), còn `router.py` chỉ là mặt HTTP của quản trị.
"""
