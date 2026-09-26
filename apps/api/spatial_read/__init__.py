"""Đọc lớp không gian của một tầng và của cả công trình (B3-02): #33, N15, N16.

Nguồn dữ liệu là ba bảng `packages/db/models/spatial.py`. Module này **chỉ đọc**: lối ghi
duy nhất nó mở ra cho người khác là `documents.ensure_document`, `entity_ids.claim_entity_ids`
(B3-03 gọi trong giao dịch ghi của mình) và lịch đối chiếu bảng đếm. Route không bao giờ ghi.

`codec.py` là nơi **duy nhất** đổi jsonb ↔ mô hình `packages.domain.spatial`; mọi chỗ khác
nhận `FloorDocument` đã giải mã, nên chỉ có một luật đọc và một luật báo hỏng
(`DocumentCorruptError`).
"""
