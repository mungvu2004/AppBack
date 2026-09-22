"""Phông 5x7 viết tay cho bản vẽ tổng hợp, phóng x2: chữ cao 14 px, nét 2 px.

Viết tay thay vì nạp phông hệ thống để bản vẽ giống nhau từng byte trên mọi máy
(M01, M06). Chỉ có chữ hoa không dấu, số, `.`, `:`, `-` và dấu cách: nhãn phòng in hoa
không dấu, chữ kích thước dạng `3.600` (`src/domain/units/parse.ts:1-17`).
"""

from collections.abc import Mapping
from functools import cache
from types import MappingProxyType
from typing import Final

import numpy as np
from numpy.typing import NDArray

SCALE: Final = 2
GLYPH_ROWS: Final = 7
GLYPH_COLS: Final = 5
TEXT_HEIGHT_PX: Final = GLYPH_ROWS * SCALE
ADVANCE_PX: Final = (GLYPH_COLS + 1) * SCALE
"""Bước ngang mỗi ký tự: 5 cột nét + 1 cột trống."""

# Mẫu kiểu HD44780: mỗi chuỗi là một hàng, `#` là điểm mực.
_ROWS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "0": ".###. #...# #..## #.#.# ##..# #...# .###.",
        "1": "..#.. .##.. ..#.. ..#.. ..#.. ..#.. .###.",
        "2": ".###. #...# ....# ...#. ..#.. .#... #####",
        "3": "##### ...#. ..#.. ...#. ....# #...# .###.",
        "4": "...#. ..##. .#.#. #..#. ##### ...#. ...#.",
        "5": "##### #.... ####. ....# ....# #...# .###.",
        "6": "..##. .#... #.... ####. #...# #...# .###.",
        "7": "##### ....# ...#. ..#.. .#... .#... .#...",
        "8": ".###. #...# #...# .###. #...# #...# .###.",
        "9": ".###. #...# #...# .#### ....# ...#. .##..",
        ".": "..... ..... ..... ..... ..... .##.. .##..",
        ":": "..... .##.. .##.. ..... .##.. .##.. .....",
        "-": "..... ..... ..... ##### ..... ..... .....",
        " ": "..... ..... ..... ..... ..... ..... .....",
        "A": ".###. #...# #...# #...# ##### #...# #...#",
        "B": "####. #...# #...# ####. #...# #...# ####.",
        "C": ".###. #...# #.... #.... #.... #...# .###.",
        "D": "###.. #..#. #...# #...# #...# #..#. ###..",
        "E": "##### #.... #.... ####. #.... #.... #####",
        "F": "##### #.... #.... ####. #.... #.... #....",
        "G": ".###. #...# #.... #.### #...# #...# .####",
        "H": "#...# #...# #...# ##### #...# #...# #...#",
        "I": ".###. ..#.. ..#.. ..#.. ..#.. ..#.. .###.",
        "J": "..### ...#. ...#. ...#. ...#. #..#. .##..",
        "K": "#...# #..#. #.#.. ##... #.#.. #..#. #...#",
        "L": "#.... #.... #.... #.... #.... #.... #####",
        "M": "#...# ##.## #.#.# #.#.# #...# #...# #...#",
        "N": "#...# #...# ##..# #.#.# #..## #...# #...#",
        "O": ".###. #...# #...# #...# #...# #...# .###.",
        "P": "####. #...# #...# ####. #.... #.... #....",
        "Q": ".###. #...# #...# #...# #.#.# #..#. .##.#",
        "R": "####. #...# #...# ####. #.#.. #..#. #...#",
        "S": ".#### #.... #.... .###. ....# ....# ####.",
        "T": "##### ..#.. ..#.. ..#.. ..#.. ..#.. ..#..",
        "U": "#...# #...# #...# #...# #...# #...# .###.",
        "V": "#...# #...# #...# #...# #...# .#.#. ..#..",
        "W": "#...# #...# #...# #.#.# #.#.# #.#.# .#.#.",
        "X": "#...# #...# .#.#. ..#.. .#.#. #...# #...#",
        "Y": "#...# #...# #...# .#.#. ..#.. ..#.. ..#..",
        "Z": "##### ....# ...#. ..#.. .#... #.... #####",
    }
)

CHARSET: Final = frozenset(_ROWS)


@cache
def glyph(char: str) -> NDArray[np.bool_]:
    """Ký tự đã phóng `(14, 10)`; ký tự ngoài phông → `ValueError`. Mảng chỉ đọc."""
    rows = _ROWS.get(char)
    if rows is None:
        raise ValueError(f"phông không có ký tự {char!r}")
    bits = np.array([[cell == "#" for cell in row] for row in rows.split()], dtype=np.bool_)
    scaled = np.kron(bits, np.ones((SCALE, SCALE), dtype=np.bool_))
    scaled.setflags(write=False)
    return scaled


def text_width_px(text: str) -> int:
    """Bề rộng khối chữ: bước ngang mỗi ký tự, bỏ cột trống sau ký tự cuối."""
    return len(text) * ADVANCE_PX - SCALE


def render_text(text: str) -> NDArray[np.bool_]:
    """Khối chữ một dòng `(14, text_width_px)`, `True` là mực; chuỗi rỗng → `ValueError`."""
    if not text:
        raise ValueError("chuỗi rỗng")
    block = np.zeros((TEXT_HEIGHT_PX, text_width_px(text)), dtype=np.bool_)
    for index, char in enumerate(text):
        left = index * ADVANCE_PX
        block[:, left : left + GLYPH_COLS * SCALE] = glyph(char)
    return block
