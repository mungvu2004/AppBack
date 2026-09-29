"""Test `apps.ml.objects.tiles` (B5-03 khối [8], phần A)."""

from itertools import pairwise

import numpy as np
import pytest

from apps.ml.objects.tiles import Window, overlap_for, tile_windows


def _coverage(width: int, height: int, windows: tuple[Window, ...]) -> np.ndarray:
    """Đếm số lát phủ mỗi điểm ảnh."""
    covered = np.zeros((height, width), dtype=np.int32)
    for w in windows:
        covered[w.y : w.y + w.height, w.x : w.x + w.width] += 1
    return covered


@pytest.mark.parametrize(
    ("width", "height", "tile", "overlap"),
    [
        (64, 64, 64, 0),
        (100, 64, 64, 16),
        (1000, 700, 640, overlap_for(640)),
        (7745, 5164, 640, overlap_for(640)),
    ],
)
def test_tile_windows__covers_every_pixel(width: int, height: int, tile: int, overlap: int) -> None:
    """Mọi điểm ảnh của trang được ít nhất một lát phủ (không lỗ hổng)."""
    windows = tile_windows(width, height, tile_px=tile, overlap_px=overlap)
    covered = _coverage(width, height, windows)
    assert (covered >= 1).all()


@pytest.mark.parametrize(
    ("width", "height", "tile", "overlap"),
    [
        (64, 64, 64, 0),
        (100, 64, 64, 16),
        (1000, 700, 640, overlap_for(640)),
        (7745, 5164, 640, overlap_for(640)),
    ],
)
def test_tile_windows__last_tile_flush_with_edges(width: int, height: int, tile: int, overlap: int) -> None:
    """Lát cuối mỗi trục sát đúng mép trang, không thừa không thiếu."""
    windows = tile_windows(width, height, tile_px=tile, overlap_px=overlap)
    assert max(w.x + w.width for w in windows) == width
    assert max(w.y + w.height for w in windows) == height


@pytest.mark.parametrize(
    ("width", "height", "tile", "overlap"),
    [
        (64, 64, 64, 0),
        (100, 64, 64, 16),
        (1000, 700, 640, overlap_for(640)),
        (7745, 5164, 640, overlap_for(640)),
    ],
)
def test_tile_windows__no_duplicate_windows(width: int, height: int, tile: int, overlap: int) -> None:
    """Không có hai cửa sổ lát trùng nhau hệt (toạ độ, khổ)."""
    windows = tile_windows(width, height, tile_px=tile, overlap_px=overlap)
    assert len(set(windows)) == len(windows)


@pytest.mark.parametrize(
    ("width", "height", "tile", "overlap"),
    [
        (100, 64, 64, 16),
        (1000, 700, 640, overlap_for(640)),
        (7745, 5164, 640, overlap_for(640)),
    ],
)
def test_tile_windows__adjacent_tiles_overlap_at_least_overlap_px(
    width: int, height: int, tile: int, overlap: int
) -> None:
    """Hai lát liền kề trên cùng trục chồng nhau ít nhất `overlap_px`."""
    windows = tile_windows(width, height, tile_px=tile, overlap_px=overlap)
    xs = sorted({w.x for w in windows})
    for a, b in pairwise(xs):
        assert (a + tile) - b >= overlap
    ys = sorted({w.y for w in windows})
    for a, b in pairwise(ys):
        assert (a + tile) - b >= overlap


@pytest.mark.parametrize(
    ("width", "height", "tile", "overlap"),
    [
        (64, 64, 64, 0),
        (100, 64, 64, 16),
        (1000, 700, 640, overlap_for(640)),
        (7745, 5164, 640, overlap_for(640)),
    ],
)
def test_tile_windows__row_major_order(width: int, height: int, tile: int, overlap: int) -> None:
    """Thứ tự cửa sổ là hàng rồi cột (khối [6] nguyên văn), không phải cột rồi hàng."""
    windows = tile_windows(width, height, tile_px=tile, overlap_px=overlap)
    keys = [(w.y, w.x) for w in windows]
    assert keys == sorted(keys)


def test_tile_windows__image_edge_at_most_tile_gives_single_position() -> None:
    """Cạnh ảnh ≤ `tile_px`: chỉ một vị trí `0`, khổ lát bằng khổ ảnh (không vượt biên)."""
    windows = tile_windows(50, 30, tile_px=64, overlap_px=0)
    assert windows == (Window(0, 0, 50, 30),)


@pytest.mark.parametrize(
    ("width", "height", "tile", "overlap"),
    [
        (0, 64, 64, 0),
        (64, 0, 64, 0),
        (64, 64, 0, 0),
        (64, 64, 64, 64),
        (64, 64, 64, 100),
        (64, 64, 64, -1),
    ],
)
def test_tile_windows__invalid_args_raise(width: int, height: int, tile: int, overlap: int) -> None:
    """Khổ/lát không dương, hay `overlap_px ≥ tile_px`, đều → `ValueError`."""
    with pytest.raises(ValueError, match="phải"):
        tile_windows(width, height, tile_px=tile, overlap_px=overlap)


def test_overlap_for__quarter_of_tile() -> None:
    """`overlap_for` là một phần tư cạnh lát (160 ở `tile_px=640`)."""
    assert overlap_for(640) == 160
