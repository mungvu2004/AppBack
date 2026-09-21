"""Bản vẽ mặt bằng tổng hợp tất định theo `seed`, kèm đáp án (bộ giả M01, tập kiểm M06).

Cùng `seed` và khổ → cùng từng byte ở mọi tiến trình: mọi lựa chọn đi qua **một**
`random.Random(seed)` (BE-00 §9), mọi hình vẽ trên lưới điểm ảnh nguyên.

- **Hình:** trắng đen, thẳng trục, không viền giấy; lưới 2-6 phòng; tường ngoài 220 mm,
  vách 110/150 mm; cửa đi 900 mm, cửa sổ 1.200 mm (chỉ tường ngoài), mọi mép cách tim
  tường vuông góc gần nhất ≥ 300 mm; 1-3 đồ mỗi phòng; nhãn phòng hoa không dấu; khung
  tên chữ góc dưới phải; chữ kích thước từng nhịp và tổng quanh tường bao.
- **Đáp án:** mặt nạ đúng điểm tường (khe `False` chỉ ở cửa đi, cửa sổ thuộc tường);
  `walls` là đường tim liền qua khe và xuyên nút T/+; hộp chữ là hộp bao mực.
- **Tô tường:** hình chữ nhật dọc trục `[floor(min - t/2), ceil(max + t/2))`, ngang trục
  đúng dải `[tâm - t/2, tâm + t/2)`; vách luôn mỏng hơn tường nó chạm nên phần nhô ở đầu
  nằm trong tường chủ.
- Dấu nhận 8x8 ô 6 px ở góc trên trái: `0xA5C3`, 32 bit `seed`, 16 bit tổng kiểm CRC-32
  của `(seed, rộng, cao)` — ảnh bị cắt đổi khổ nên dấu không còn khớp.
"""

import hashlib
import itertools
import math
import random
import struct
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

import numpy as np
from numpy.typing import NDArray

from packages.ml_contracts._font import TEXT_HEIGHT_PX, render_text, text_width_px
from packages.ml_contracts._png import MASK_MAX_PIXELS, encode_rgb_png
from packages.ml_contracts.artifacts import BoxPx, DetectionPx, PointPx, TextPx, WallPx
from packages.ml_contracts.labels import DetectionLabel

MIN_EDGE_PX: Final = 256
MAX_SEED: Final = 2**32 - 1
EVAL_SET_SEEDS: Final = range(100, 140)
EVAL_SET_SHA256: Final = "c9f98590281847704541a4cfbf73e21b73a93e132d262318eebdd8f071f6c3b3"
"""SHA-256 của `pixels.tobytes() + walls_mask.tobytes()` nối theo `EVAL_SET_SEEDS` (không băm PNG).

Đổi hằng này là đổi tập kiểm cố định: chỉ qua FIX kèm đánh giá lại mọi phiên bản (M06).
"""

MM_PER_PX_CHOICES: Final = (8.0, 10.0, 12.5)
OUTER_WALL_MM: Final = 220
PARTITION_MM: Final = (110, 150)
DOOR_MM: Final = 900
WINDOW_MM: Final = 1200
CLEARANCE_MM: Final = 300
ROOM_MM: Final = (2400, 4800)
FURNITURE_MARGIN_MM: Final = 150
MAX_BUILDING_PX: Final = (1000, 700)
"""Trần khổ nhà (tim-tim): nhà lớn quá thì mực tường lấn mực chữ, luật ≥ 5 % mực ngoài hộp tường hỏng."""

PAGE_MARGIN_PX: Final = 16
SPAN_TEXT_GAP_PX: Final = 3 * TEXT_HEIGHT_PX
TOTAL_TEXT_GAP_PX: Final = 6 * TEXT_HEIGHT_PX
_DIM_BAND_PX: Final = TOTAL_TEXT_GAP_PX + TEXT_HEIGHT_PX
_SIDE_RESERVE_PX: Final = _DIM_BAND_PX + PAGE_MARGIN_PX
_TITLE_LINE_GAP_PX: Final = 6
_LABEL_GAP_PX: Final = 4

MARKER_MAGIC: Final = 0xA5C3
MARKER_CELL_PX: Final = 6
MARKER_GRID: Final = 8
MARKER_SIZE_PX: Final = MARKER_CELL_PX * MARKER_GRID

_ROOM_NAMES: Final = ("PHONG KHACH", "PHONG NGU", "PHONG AN", "LAM VIEC", "BEP", "KHO", "SANH", "WC")
_FURNITURE_MM: Final[dict[DetectionLabel, tuple[int, int]]] = {
    "table": (1200, 800),
    "chair": (450, 450),
    "bed": (1600, 2000),
    "wardrobe": (1200, 600),
    "kitchen_cabinet": (1800, 600),
    "sanitary_fixture": (400, 700),
    "stair": (1000, 2400),
}
_TITLE_CHOICES: Final = (
    ("BAN VE MAT BANG",),
    ("NHA O RIENG LE", "NHA PHO LIEN KE", "VAN PHONG NHO", "CAN HO CHUNG CU"),
    ("TANG TRET", "TANG MOT", "TANG HAI", "TANG LUNG"),
    ("KIEN TRUC",),
    ("THIET KE SO BO", "THIET KE KY THUAT", "HO SO XIN PHEP"),
)
_TITLE_HEIGHT_PX: Final = len(_TITLE_CHOICES) * (TEXT_HEIGHT_PX + _TITLE_LINE_GAP_PX) - _TITLE_LINE_GAP_PX
_BOTTOM_RESERVE_PX: Final = _DIM_BAND_PX + 2 * _LABEL_GAP_PX + _TITLE_HEIGHT_PX + PAGE_MARGIN_PX


@dataclass(frozen=True, slots=True)
class SyntheticPlan:
    """Một trang tổng hợp và đáp án của nó. Mảng chỉ đọc (bộ giả trả chúng dùng chung)."""

    seed: int
    pixels: NDArray[np.uint8]
    image_png: bytes
    walls_mask: NDArray[np.bool_]
    walls: tuple[WallPx, ...]
    detections: tuple[DetectionPx, ...]
    texts: tuple[TextPx, ...]
    mm_per_px: float


@dataclass(frozen=True, slots=True)
class _Wall:
    """Một tường đang dựng: dải ngang trục `[lo, lo + t)`, tim dọc trục từ `start` tới `end`."""

    horizontal: bool
    lo: int
    thickness: int
    start: float
    end: float

    @property
    def centre(self) -> float:
        """Toạ độ tim ngang trục."""
        return self.lo + self.thickness / 2

    def rect(self) -> tuple[int, int, int, int]:
        """`(y0, y1, x0, x1)` phải tô theo luật tô tường của module."""
        half = self.thickness / 2
        a0, a1 = math.floor(self.start - half), math.ceil(self.end + half)
        c0, c1 = self.lo, self.lo + self.thickness
        return (c0, c1, a0, a1) if self.horizontal else (a0, a1, c0, c1)


@dataclass(slots=True)
class _Canvas:
    """Trạng thái vẽ: mực, mặt nạ tường và các đáp án đã sinh."""

    ink: NDArray[np.bool_]
    mask: NDArray[np.bool_]
    detections: list[DetectionPx] = field(default_factory=list)
    texts: list[TextPx] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Grid:
    """Lưới phòng: tường dọc (trái → phải), tường ngang (trên → dưới), tỉ lệ."""

    verticals: tuple[_Wall, ...]
    horizontals: tuple[_Wall, ...]
    mm_per_px: float


def _px(mm: float, mm_per_px: float) -> int:
    """mm → số điểm ảnh, làm tròn nửa lên (`floor(x + 0.5)`)."""
    return math.floor(mm / mm_per_px + 0.5)


def format_mm(value: int) -> str:
    """Chữ kích thước kiểu Việt `3.600` (nhóm nghìn bằng dấu chấm, `parse.ts:1-17`)."""
    return f"{value:,}".replace(",", ".")


def _room_sizes(rng: random.Random, count: int, low: int, high: int, limit: int) -> list[int]:
    """`count` khoảng tim-tim trong `[low, high]`, tổng ≤ `limit` (cắt phòng lớn nhất trước)."""
    sizes = [rng.randint(low, high) for _ in range(count)]
    excess = sum(sizes) - limit
    for index in sorted(range(count), key=lambda item: -sizes[item]):
        cut = max(0, min(excess, sizes[index] - low))
        sizes[index] -= cut
        excess -= cut
    return sizes


def _limits(width: int, height: int, mm_per_px: float) -> tuple[int, int]:
    """Khổ tim-tim tối đa của nhà trên trang, chừa dải chữ bốn phía và khung tên."""
    outer = _px(OUTER_WALL_MM, mm_per_px)
    return (
        min(MAX_BUILDING_PX[0], width - 2 * _SIDE_RESERVE_PX - outer),
        min(MAX_BUILDING_PX[1], height - _SIDE_RESERVE_PX - _BOTTOM_RESERVE_PX - outer),
    )


def _grid_choices(width: int, height: int, mm_per_px: float) -> list[tuple[int, int]]:
    """Mọi lưới `(cột, hàng)` 2-6 phòng vừa trang ở tỉ lệ này."""
    room_min = math.ceil(ROOM_MM[0] / mm_per_px)
    max_w, max_h = _limits(width, height, mm_per_px)
    return [
        (cols, rows)
        for cols in range(1, 7)
        for rows in range(1, 7)
        if 2 <= cols * rows <= 6 and cols * room_min <= max_w and rows * room_min <= max_h
    ]


def _axis(rng: random.Random, count: int, mm_per_px: float, limit: int, room_max: int) -> tuple[list[int], list[int]]:
    """(tim nguyên của các tường theo một trục tính từ tường đầu, bề dày px từng tường)."""
    sizes = _room_sizes(rng, count, math.ceil(ROOM_MM[0] / mm_per_px), room_max, limit)
    centres = [0]
    for size in sizes:
        centres.append(centres[-1] + size)
    outer = _px(OUTER_WALL_MM, mm_per_px)
    thickness = [outer, *(_px(rng.choice(PARTITION_MM), mm_per_px) for _ in range(count - 1)), outer]
    return centres, thickness


def _layout(rng: random.Random, width: int, height: int) -> _Grid:
    """Chọn tỉ lệ, lưới, khổ phòng và vị trí nhà; trang quá nhỏ cho mọi lưới → `ValueError`."""
    scales = [scale for scale in MM_PER_PX_CHOICES if _grid_choices(width, height, scale)]
    if not scales:
        raise ValueError(f"trang {width}x{height} quá nhỏ cho bản vẽ tối thiểu (2 phòng, chữ kích thước, khung tên)")
    mm_per_px = rng.choice(scales)
    cols, rows = rng.choice(_grid_choices(width, height, mm_per_px))
    max_w, max_h = _limits(width, height, mm_per_px)
    room_max = math.floor(ROOM_MM[1] / mm_per_px)
    xs, x_thick = _axis(rng, cols, mm_per_px, max_w, room_max)
    ys, y_thick = _axis(rng, rows, mm_per_px, max_h, room_max)
    half = x_thick[0] // 2
    left = rng.randint(_SIDE_RESERVE_PX, width - _SIDE_RESERVE_PX - xs[-1] - 2 * half) + half
    top = rng.randint(_SIDE_RESERVE_PX, height - _BOTTOM_RESERVE_PX - ys[-1] - 2 * half) + half
    x_lo = [left + x - t // 2 for x, t in zip(xs, x_thick, strict=True)]
    y_lo = [top + y - t // 2 for y, t in zip(ys, y_thick, strict=True)]
    x_mid = [lo + t / 2 for lo, t in zip(x_lo, x_thick, strict=True)]
    y_mid = [lo + t / 2 for lo, t in zip(y_lo, y_thick, strict=True)]
    verticals = tuple(_Wall(False, lo, t, y_mid[0], y_mid[-1]) for lo, t in zip(x_lo, x_thick, strict=True))
    horizontals = tuple(_Wall(True, lo, t, x_mid[0], x_mid[-1]) for lo, t in zip(y_lo, y_thick, strict=True))
    return _Grid(verticals, horizontals, mm_per_px)


def _box(x0: float, y0: float, x1: float, y1: float) -> BoxPx:
    """Hộp đáp án từ mép điểm ảnh."""
    return BoxPx(x_min=x0, y_min=y0, x_max=x1, y_max=y1)


def _gap(host: _Wall, along0: int, along1: int) -> tuple[int, int, int, int]:
    """`(y0, y1, x0, x1)` của khe trên dải tường chủ, dọc trục từ `along0` tới `along1`."""
    c0, c1 = host.lo, host.lo + host.thickness
    return (c0, c1, along0, along1) if host.horizontal else (along0, along1, c0, c1)


def _place(rng: random.Random, span: tuple[float, float], width_mm: int, mm_per_px: float) -> tuple[int, int]:
    """Đoạn `[d0, d1)` rộng `width_mm` trong nhịp, hai mép cách tim tường vuông góc ≥ 300 mm."""
    width = _px(width_mm, mm_per_px)
    clearance = CLEARANCE_MM / mm_per_px
    low = math.ceil(span[0] + clearance)
    start = rng.randint(low, math.floor(span[1] - clearance) - width)
    return start, start + width


def _door(canvas: _Canvas, rng: random.Random, host: _Wall, span: tuple[float, float], mm_per_px: float) -> None:
    """Cửa đi: khe trống ở cả ảnh và mặt nạ."""
    d0, d1 = _place(rng, span, DOOR_MM, mm_per_px)
    y0, y1, x0, x1 = _gap(host, d0, d1)
    canvas.ink[y0:y1, x0:x1] = False
    canvas.mask[y0:y1, x0:x1] = False
    canvas.detections.append(DetectionPx(label="door", box=_box(x0, y0, x1, y1), confidence=1.0))


def _window(canvas: _Canvas, rng: random.Random, host: _Wall, span: tuple[float, float], mm_per_px: float) -> None:
    """Cửa sổ: khe trên ảnh với 3 nét 1 px song song tường; mặt nạ giữ nguyên là tường."""
    d0, d1 = _place(rng, span, WINDOW_MM, mm_per_px)
    y0, y1, x0, x1 = _gap(host, d0, d1)
    canvas.ink[y0:y1, x0:x1] = False
    for offset in (0, host.thickness // 2, host.thickness - 1):
        line = host.lo + offset
        if host.horizontal:
            canvas.ink[line, x0:x1] = True
        else:
            canvas.ink[y0:y1, line] = True
    canvas.detections.append(DetectionPx(label="window", box=_box(x0, y0, x1, y1), confidence=1.0))


def _spans(walls: Sequence[_Wall]) -> list[tuple[float, float]]:
    """Các nhịp tim-tim giữa những tường liên tiếp."""
    return [(a.centre, b.centre) for a, b in itertools.pairwise(walls)]


def _interior_doors(canvas: _Canvas, rng: random.Random, grid: _Grid) -> None:
    """Cửa giữa các phòng theo một cây khung ngẫu nhiên: phòng nào cũng tới được."""
    cols, rows = len(grid.verticals) - 1, len(grid.horizontals) - 1
    visited = {(rng.randrange(cols), rng.randrange(rows))}
    while len(visited) < cols * rows:
        edges = sorted(
            (room, (room[0] + dx, room[1] + dy))
            for room in visited
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if 0 <= room[0] + dx < cols and 0 <= room[1] + dy < rows and (room[0] + dx, room[1] + dy) not in visited
        )
        (ax, ay), (bx, by) = rng.choice(edges)
        visited.add((bx, by))
        if ay == by:
            _door(canvas, rng, grid.verticals[max(ax, bx)], _spans(grid.horizontals)[ay], grid.mm_per_px)
        else:
            _door(canvas, rng, grid.horizontals[max(ay, by)], _spans(grid.verticals)[ax], grid.mm_per_px)


def _outer_openings(canvas: _Canvas, rng: random.Random, grid: _Grid) -> None:
    """Một cửa đi vào nhà trên tường bao; cửa sổ ở một nửa số nhịp còn lại, ít nhất một."""
    slots = [
        (host, span)
        for hosts, crossing in ((grid.horizontals, grid.verticals), (grid.verticals, grid.horizontals))
        for host in (hosts[0], hosts[-1])
        for span in _spans(crossing)
    ]
    entrance = rng.randrange(len(slots))
    _door(canvas, rng, *slots[entrance], grid.mm_per_px)
    rest = [slot for index, slot in enumerate(slots) if index != entrance]
    windows = [slot for slot in rest if rng.random() < 0.5] or [rng.choice(rest)]
    for host, span in windows:
        _window(canvas, rng, host, span, grid.mm_per_px)


def _stamp(canvas: _Canvas, block: NDArray[np.bool_], x0: int, y0: int, text: str) -> None:
    """Đặt khối chữ và ghi đáp án với hộp bao mực thật (không phải hộp bố cục)."""
    height, width = block.shape
    canvas.ink[y0 : y0 + height, x0 : x0 + width] |= block
    rows = np.flatnonzero(block.any(axis=1))
    cols = np.flatnonzero(block.any(axis=0))
    box = _box(x0 + cols[0], y0 + rows[0], x0 + cols[-1] + 1, y0 + rows[-1] + 1)
    canvas.texts.append(TextPx(text=text, box=box, confidence=1.0))


def _room_label(canvas: _Canvas, rng: random.Random, room: tuple[int, int, int, int], margin: int) -> None:
    """Nhãn phòng hoa không dấu ở giữa phòng, chọn trong các tên vừa bề rộng."""
    ix0, iy0, ix1, iy1 = room
    name = rng.choice([name for name in _ROOM_NAMES if text_width_px(name) <= ix1 - ix0 - 2 * margin])
    block = render_text(name)
    _stamp(canvas, block, _centred((ix0 + ix1) / 2, block.shape[1]), _centred((iy0 + iy1) / 2, TEXT_HEIGHT_PX), name)


def _furniture(canvas: _Canvas, rng: random.Random, room: tuple[int, int, int, int], mm_per_px: float) -> None:
    """1-3 đồ ở góc phòng; mỗi đồ gọn trong một phần tư, phía trên/dưới dải nhãn nên không chạm nhãn."""
    ix0, iy0, ix1, iy1 = room
    margin = _px(FURNITURE_MARGIN_MM, mm_per_px)
    quarter_w = (ix1 - ix0) // 2 - margin - _LABEL_GAP_PX
    quarter_h = (iy1 - iy0 - TEXT_HEIGHT_PX) // 2 - margin - _LABEL_GAP_PX
    for corner in sorted(rng.sample(range(4), rng.randint(1, 3))):
        label = rng.choice(sorted(_FURNITURE_MM))
        w_mm, h_mm = _FURNITURE_MM[label] if rng.random() < 0.5 else _FURNITURE_MM[label][::-1]
        w, h = min(_px(w_mm, mm_per_px), quarter_w), min(_px(h_mm, mm_per_px), quarter_h)
        x0 = ix0 + margin if corner % 2 == 0 else ix1 - margin - w
        y0 = iy0 + margin if corner < 2 else iy1 - margin - h
        _outline(canvas, x0, y0, x0 + w, y0 + h)
        canvas.detections.append(DetectionPx(label=label, box=_box(x0, y0, x0 + w, y0 + h), confidence=1.0))


def _rooms(canvas: _Canvas, rng: random.Random, grid: _Grid) -> None:
    """Nhãn và đồ của từng phòng, theo hàng rồi cột."""
    margin = _px(FURNITURE_MARGIN_MM, grid.mm_per_px)
    for top, bottom in itertools.pairwise(grid.horizontals):
        for left, right in itertools.pairwise(grid.verticals):
            room = (left.lo + left.thickness, top.lo + top.thickness, right.lo, bottom.lo)
            _room_label(canvas, rng, room, margin)
            _furniture(canvas, rng, room, grid.mm_per_px)


def _outline(canvas: _Canvas, x0: int, y0: int, x1: int, y1: int) -> None:
    """Viền 1 px của hình chữ nhật `[x0, x1) x [y0, y1)`."""
    canvas.ink[y0, x0:x1] = True
    canvas.ink[y1 - 1, x0:x1] = True
    canvas.ink[y0:y1, x0] = True
    canvas.ink[y0:y1, x1 - 1] = True


def _centred(mid: float, size: int) -> int:
    """Mép đầu của khối dài `size` có tâm ở `mid`, làm tròn nửa lên."""
    return math.floor(mid - size / 2 + 0.5)


def _dimension_text(canvas: _Canvas, side: str, face: int, span: tuple[float, float], gap: int, scale: float) -> None:
    """Một chữ kích thước song song cạnh `side`, tâm giữa nhịp, mép gần cách mặt ngoài `gap`.

    Giá trị là nhịp tim-tim đổi ra mm, `floor(x + 0.5)`. Cạnh đứng xoay chữ 90° theo
    chiều kim đồng hồ (đọc từ trên xuống).
    """
    text = format_mm(math.floor((span[1] - span[0]) * scale + 0.5))
    block = render_text(text)
    if side in ("left", "right"):
        block = np.rot90(block, k=-1)
    height, width = block.shape
    mid = (span[0] + span[1]) / 2
    positions = {
        "top": (_centred(mid, width), face - gap - height),
        "bottom": (_centred(mid, width), face + gap),
        "left": (face - gap - width, _centred(mid, height)),
        "right": (face + gap, _centred(mid, height)),
    }
    _stamp(canvas, block, *positions[side], text)


def _dimensions(canvas: _Canvas, grid: _Grid) -> None:
    """Mỗi cạnh tường bao: hàng chữ từng nhịp (cách 3 x cao chữ) và chữ tổng (cách 6 x cao chữ)."""
    top, bottom = grid.horizontals[0], grid.horizontals[-1]
    left, right = grid.verticals[0], grid.verticals[-1]
    sides = (
        ("top", top.lo, grid.verticals),
        ("bottom", bottom.lo + bottom.thickness, grid.verticals),
        ("left", left.lo, grid.horizontals),
        ("right", right.lo + right.thickness, grid.horizontals),
    )
    for side, face, crossing in sides:
        for span in _spans(crossing):
            _dimension_text(canvas, side, face, span, SPAN_TEXT_GAP_PX, grid.mm_per_px)
        whole = (crossing[0].centre, crossing[-1].centre)
        _dimension_text(canvas, side, face, whole, TOTAL_TEXT_GAP_PX, grid.mm_per_px)


def _title_block(canvas: _Canvas, rng: random.Random) -> None:
    """Khung tên chữ canh phải ở góc dưới phải, dòng cuối cách mép trang `PAGE_MARGIN_PX`."""
    height, width = canvas.ink.shape
    lines = [rng.choice(options) for options in _TITLE_CHOICES]
    bottom = height - PAGE_MARGIN_PX
    for line in reversed(lines):
        block = render_text(line)
        _stamp(canvas, block, width - PAGE_MARGIN_PX - block.shape[1], bottom - TEXT_HEIGHT_PX, line)
        bottom -= TEXT_HEIGHT_PX + _TITLE_LINE_GAP_PX


def _marker_value(seed: int, width: int, height: int) -> int:
    """64 bit của dấu: `0xA5C3`, `seed`, 16 bit thấp của CRC-32 `(seed, rộng, cao)`."""
    checksum = zlib.crc32(struct.pack(">III", seed, width, height)) & 0xFFFF
    return (MARKER_MAGIC << 48) | (seed << 16) | checksum


def _draw_marker(canvas: _Canvas, seed: int) -> None:
    """Dấu 8x8 ô ở góc trên trái, bit cao nhất trước, theo hàng; ô đen = bit 1."""
    height, width = canvas.ink.shape
    value = _marker_value(seed, width, height)
    bits = MARKER_GRID * MARKER_GRID
    for index in range(bits):
        if (value >> (bits - 1 - index)) & 1:
            row, col = divmod(index, MARKER_GRID)
            cell = MARKER_CELL_PX
            canvas.ink[row * cell : (row + 1) * cell, col * cell : (col + 1) * cell] = True


def read_marker(image: NDArray[np.uint8]) -> int | None:
    """`seed` của trang tổng hợp khi dấu đúng **và** khớp khổ ảnh; còn lại (kể cả ảnh bị cắt) → `None`."""
    if image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < MARKER_SIZE_PX:
        return None
    region = image[:MARKER_SIZE_PX, :MARKER_SIZE_PX].reshape(
        MARKER_GRID, MARKER_CELL_PX, MARKER_GRID, MARKER_CELL_PX, 3
    )
    cells = region.mean(axis=(1, 3, 4)) < 128
    value = int("".join("1" if bit else "0" for bit in cells.ravel()), 2)
    seed = (value >> 16) & MAX_SEED
    height, width = image.shape[:2]
    return seed if value == _marker_value(seed, width, height) else None


def _answer_wall(wall: _Wall) -> WallPx:
    """Đáp án một tường: đường tim liền từ đầu tới cuối, bề dày đúng dải đã tô."""
    centre = wall.centre
    if wall.horizontal:
        start, end = PointPx(x=wall.start, y=centre), PointPx(x=wall.end, y=centre)
    else:
        start, end = PointPx(x=centre, y=wall.start), PointPx(x=centre, y=wall.end)
    return WallPx(start=start, end=end, thickness_px=float(wall.thickness), confidence=1.0)


def _readonly[ArrayT: np.ndarray[tuple[int, ...], np.dtype[np.generic]]](array: ArrayT) -> ArrayT:
    """Khoá ghi: bộ giả trả chính mảng này cho mọi người gọi (LRU)."""
    array.setflags(write=False)
    return array


def _check_request(seed: int, width_px: int, height_px: int) -> None:
    """`seed` 32 bit; cạnh ≥ `MIN_EDGE_PX`, tổng điểm ≤ `MASK_MAX_PIXELS`."""
    if not 0 <= seed <= MAX_SEED:
        raise ValueError(f"seed ngoài 0..{MAX_SEED}: {seed}")
    if min(width_px, height_px) < MIN_EDGE_PX or width_px * height_px > MASK_MAX_PIXELS:
        raise ValueError(f"khổ {width_px}x{height_px}: cạnh ≥ {MIN_EDGE_PX}, tổng ≤ {MASK_MAX_PIXELS} điểm")


def render_plan(seed: int, *, width_px: int = 1600, height_px: int = 1200) -> SyntheticPlan:
    """Vẽ trang tổng hợp của `seed` (0…2^32-1) trên khổ `width_px x height_px`.

    Tham số sai, hay trang không đủ chỗ cho bản vẽ tối thiểu (2 phòng, chữ kích thước,
    khung tên) → `ValueError`.
    """
    _check_request(seed, width_px, height_px)
    rng = random.Random(seed)  # noqa: S311 — dữ liệu tổng hợp tất định theo seed, không phải bí mật
    grid = _layout(rng, width_px, height_px)
    shape = (height_px, width_px)
    canvas = _Canvas(ink=np.zeros(shape, dtype=np.bool_), mask=np.zeros(shape, dtype=np.bool_))
    walls = (*grid.horizontals, *grid.verticals)
    for wall in walls:
        y0, y1, x0, x1 = wall.rect()
        canvas.mask[y0:y1, x0:x1] = True
    canvas.ink |= canvas.mask
    _interior_doors(canvas, rng, grid)
    _outer_openings(canvas, rng, grid)
    _rooms(canvas, rng, grid)
    _dimensions(canvas, grid)
    _title_block(canvas, rng)
    _draw_marker(canvas, seed)
    pixels = np.repeat(np.where(canvas.ink, 0, 255).astype(np.uint8)[:, :, None], 3, axis=2)
    return SyntheticPlan(
        seed=seed,
        pixels=_readonly(pixels),
        image_png=encode_rgb_png(pixels),
        walls_mask=_readonly(canvas.mask),
        walls=tuple(_answer_wall(wall) for wall in walls),
        detections=tuple(canvas.detections),
        texts=tuple(canvas.texts),
        mm_per_px=grid.mm_per_px,
    )


def eval_set_digest() -> str:
    """SHA-256 của tập kiểm cố định, tính lại từ `render_plan` (so với `EVAL_SET_SHA256`, M06)."""
    digest = hashlib.sha256()
    for seed in EVAL_SET_SEEDS:
        plan = render_plan(seed)
        digest.update(plan.pixels.tobytes())
        digest.update(plan.walls_mask.tobytes())
    return digest.hexdigest()
