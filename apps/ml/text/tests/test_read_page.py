"""`read_page`: đọc lại trên ảnh phóng + giãn mức xám chỉ khi lượt thường chưa ra tỉ lệ chuỗi kích thước."""

import numpy as np
from numpy.typing import NDArray

from apps.ml.text.tasks import REREAD_MAX_SIDE_PX, REREAD_ZOOM, _stretch, read_page
from packages.ml_contracts.artifacts import BoxPx, TextPx

_ROWS = (100, 200, 300)


def _page(width: int = 400, height: int = 400) -> NDArray[np.uint8]:
    """Ba đường kích thước 50-150 (dài 100 px, vạch đầu đoạn) ở `_ROWS`, nền trắng."""
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    for row in _ROWS:
        image[row, 50:151] = 225
        image[row : row + 16, (50, 150)] = 225
    return image


def _chain_texts(zoom: float) -> tuple[TextPx, ...]:
    """`1000` nằm giữa mỗi đường (10 mm/px), hộp theo toạ độ ảnh phóng `zoom` lần."""
    return tuple(
        TextPx(
            text="1000",
            box=BoxPx(x_min=85 * zoom, y_min=(row - 16) * zoom, x_max=115 * zoom, y_max=(row - 2) * zoom),
            confidence=0.9,
        )
        for row in _ROWS
    )


class _Reader:
    """Bộ đọc giả: ảnh gốc trả `base`, ảnh phóng trả `zoomed`; ghi khổ ảnh mỗi lượt."""

    def __init__(self, base: tuple[TextPx, ...], zoomed: tuple[TextPx, ...]) -> None:
        """Chữ trả cho lượt đầu và các lượt sau."""
        self.base, self.zoomed = base, zoomed
        self.shapes: list[tuple[int, ...]] = []

    def read(self, image: NDArray[np.uint8]) -> tuple[TextPx, ...]:
        """Lượt đầu trả `base`, các lượt sau trả `zoomed`."""
        self.shapes.append(image.shape[:2])
        return self.zoomed if len(self.shapes) > 1 else self.base


def test_read_page_rereads_zoomed_when_no_chain_scale() -> None:
    """Lượt thường không có chữ kích thước; lượt phóng thấy 3 chữ → nhận, hộp chia lại, span đo trên ảnh gốc."""
    reader = _Reader((), _chain_texts(REREAD_ZOOM))
    items = read_page(_page(), reader)
    assert reader.shapes == [(400, 400), (800, 800)]
    assert [item.box for item in items] == [item.box for item in _chain_texts(1)]
    assert [item.span_px for item in items] == [100.0] * 3


def test_read_page_keeps_first_pass_when_chain_scale_found() -> None:
    """Lượt thường đã ra tỉ lệ → một lượt duy nhất (không tốn thêm, không đổi chữ của ca chuỗi đang đúng)."""
    reader = _Reader(_chain_texts(1), ())
    assert [item.span_px for item in read_page(_page(), reader)] == [100.0] * 3
    assert len(reader.shapes) == 1


def test_read_page_keeps_first_pass_when_reread_finds_no_scale() -> None:
    """Lượt phóng cũng không ra tỉ lệ → giữ chữ lượt thường (nhãn phòng…), không lấy lượt phóng."""
    room = TextPx(text="PN1", box=BoxPx(x_min=250, y_min=350, x_max=280, y_max=364), confidence=0.9)
    reader = _Reader((room,), _chain_texts(REREAD_ZOOM)[:1])
    assert [item.text for item in read_page(_page(), reader)] == ["PN1"]
    assert len(reader.shapes) == 2


def test_read_page_skips_reread_on_large_page() -> None:
    """Trang cạnh dài ≥ `REREAD_MAX_SIDE_PX` không đọc lại."""
    reader = _Reader((), _chain_texts(REREAD_ZOOM))
    assert read_page(_page(width=REREAD_MAX_SIDE_PX), reader) == ()
    assert len(reader.shapes) == 1


def test_stretch_maps_background_to_white_and_ink_to_black() -> None:
    """Nền 200, chữ 150 → nền 255, chữ 0; ảnh gần trống giữ nguyên."""
    image = np.full((20, 20, 3), 200, dtype=np.uint8)
    image[:5, :5] = 150
    stretched = _stretch(image)
    assert int(stretched[10, 10, 0]) == 255
    assert int(stretched[0, 0, 0]) == 0
    flat = np.full((20, 20, 3), 200, dtype=np.uint8)
    assert _stretch(flat) is flat
