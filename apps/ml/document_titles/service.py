"""Phần thuần của task: cắt dải tiêu đề quanh vùng, OCR, đổi hộp chữ về tỉ lệ trang, dựng JSON."""

import json
from collections.abc import Sequence
from typing import Final, Literal

import numpy as np
from numpy.typing import NDArray

from packages.ml_contracts.ports import TextReader

TITLE_BAND_RATIO: Final = 0.15  # cùng dải 15 % chiều cao vùng như `packages.vision.drawing_kind`

type RatioBox = tuple[float, float, float, float]
type TitleItem = dict[str, object]


def title_bands(boxes: Sequence[RatioBox], width: int, height: int) -> list[tuple[int, int, int, int]]:
    """Dải pixel `(x0, y0, x1, y1)` ngay trên và ngay dưới mỗi hộp vùng, kẹp vào trang; bỏ dải rỗng."""
    bands: list[tuple[int, int, int, int]] = []
    for x0, y0, x1, y1 in boxes:
        band = TITLE_BAND_RATIO * (y1 - y0)
        for top, bottom in ((y0 - band, y0), (y1, y1 + band)):
            rect = (int(x0 * width), int(max(0.0, top) * height), int(x1 * width), int(min(1.0, bottom) * height))
            if rect[2] > rect[0] and rect[3] > rect[1]:
                bands.append(rect)
    return bands


def read_titles(image: NDArray[np.uint8], boxes: Sequence[RatioBox], reader: TextReader) -> list[TitleItem]:
    """OCR từng dải tiêu đề; hộp chữ đổi về tỉ lệ TRANG; chữ trùng (hai dải chồng nhau) chỉ giữ một."""
    height, width = image.shape[:2]
    seen: dict[tuple[str, RatioBox], TitleItem] = {}
    for bx0, by0, bx1, by1 in title_bands(boxes, width, height):
        for item in reader.read(np.ascontiguousarray(image[by0:by1, bx0:bx1])):
            box = (
                round((bx0 + item.box.x_min) / width, 6),
                round((by0 + item.box.y_min) / height, 6),
                round((bx0 + item.box.x_max) / width, 6),
                round((by0 + item.box.y_max) / height, 6),
            )
            seen.setdefault((item.text, box), {"text": item.text, "box": list(box)})
    return [seen[k] for k in sorted(seen)]


def titles_json(status: Literal["ok", "skipped"], texts: Sequence[TitleItem]) -> bytes:
    """`{"status", "texts"}` ổn định (khoá sắp xếp) để giao lặp ghi đè đúng bytes cũ (J06)."""
    return json.dumps({"status": status, "texts": list(texts)}, ensure_ascii=False, sort_keys=True).encode()
