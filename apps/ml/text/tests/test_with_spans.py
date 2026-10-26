"""`with_spans`: bước đọc chữ gắn đoạn kích thước đo trên ảnh vào từng mục `text.json`."""

import numpy as np

from apps.ml.text.tasks import with_spans
from packages.ml_contracts.artifacts import BoxPx, TextPx


def test_with_spans__measures_chain_and_leaves_room_label_empty() -> None:
    """Chữ trên chuỗi 50-150 (RGB nền trắng, đường nhạt) có `span_px` 100; nhãn phòng đứng riêng → `None`."""
    image = np.full((220, 400, 3), 255, dtype=np.uint8)
    image[100, 50:151] = 225
    image[100:116, (50, 150)] = 225
    on_chain = TextPx(text="1000", box=BoxPx(x_min=85, y_min=84, x_max=115, y_max=98), confidence=0.9)
    room = TextPx(text="PN1", box=BoxPx(x_min=250, y_min=180, x_max=280, y_max=194), confidence=0.9)
    assert [item.span_px for item in with_spans(image, (on_chain, room))] == [100.0, None]


def test_with_spans__no_items_returns_input() -> None:
    """Trang không có chữ: trả lại đúng bộ rỗng, không dựng mặt nạ."""
    assert with_spans(np.zeros((4, 4, 3), dtype=np.uint8), ()) == ()
