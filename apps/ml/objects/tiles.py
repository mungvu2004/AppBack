"""Lưới lát ảnh cho suy luận YOLO theo cửa sổ trượt (B5-03 khối [6] "Lưới lát").

Toạ độ tính trên **lát**, không lặp Python theo điểm ảnh (K28): `range` trên các bước
`x`/`y` rồi thêm lát cuối sát mép nếu còn hở, không giữ mảng ảnh nào trong bộ nhớ.
"""

from typing import Final, NamedTuple


class Window(NamedTuple):
    """Một cửa sổ lát vuông góc trục: `(x, y)` là góc trên-trái, đơn vị pixel."""

    x: int
    y: int
    width: int
    height: int


def overlap_for(tile_px: int) -> int:
    """Độ chồng mặc định của detector: một phần tư cạnh lát (160 ở `tile_px=640`)."""
    return tile_px // 4


def _starts(length: int, tile: int, step: int) -> tuple[int, ...]:
    """Toạ độ bắt đầu theo một trục: `0, step, 2·step, …` cộng lát cuối sát mép nếu chưa phủ hết."""
    if length <= tile:
        return (0,)
    positions = list(range(0, length - tile + 1, step))
    last = length - tile
    if positions[-1] != last:
        positions.append(last)
    return tuple(positions)


def tile_windows(width_px: int, height_px: int, *, tile_px: int, overlap_px: int) -> tuple[Window, ...]:
    """Mọi cửa sổ lát phủ `width_px x height_px`, thứ tự hàng rồi cột (B5-03 khối [6] nguyên văn).

    `overlap_px ≥ tile_px` hay bất kỳ kích thước nào `≤ 0` (trừ `overlap_px = 0`) → `ValueError`.
    Cạnh ảnh `≤ tile_px` chỉ có một vị trí `0`, cạnh lát = cạnh ảnh đó (lát không vượt biên).
    """
    if width_px <= 0 or height_px <= 0 or tile_px <= 0 or overlap_px < 0:
        raise ValueError("width_px, height_px, tile_px phải dương; overlap_px không âm")
    if overlap_px >= tile_px:
        raise ValueError("overlap_px phải nhỏ hơn tile_px")
    step: Final = tile_px - overlap_px
    xs = _starts(width_px, tile_px, step)
    ys = _starts(height_px, tile_px, step)
    tile_w = min(tile_px, width_px)
    tile_h = min(tile_px, height_px)
    return tuple(Window(x, y, tile_w, tile_h) for y in ys for x in xs)
