"""Bảng ảnh ứng viên đánh số (Pillow): AI chỉ thấy số ô + số đo, không thấy tên/id mẫu."""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from typing import Final

from PIL import Image, ImageDraw, UnidentifiedImageError

from apps.worker.design_director.fill import load_font
from packages.domain.design_director.profiles import Profile

__all__ = ["CELL_PX", "contact_sheet"]

CELL_PX: Final = 220
COLS_MAX: Final = 6
_CAPTION_PX: Final = 46
_SWATCH: Final = (200, 200, 200)


def _paste_preview(im: Image.Image, data: bytes | None, x: int, y: int) -> bool:
    """Dán ảnh xem trước (nền xám nhạt dưới phần trong suốt); ảnh hỏng/vắng → `False`."""
    if not data:
        return False
    try:
        thumb = Image.open(io.BytesIO(data)).convert("RGBA")
    except (UnidentifiedImageError, OSError):
        return False
    thumb.thumbnail((CELL_PX - 12, CELL_PX - 12))
    bg = Image.new("RGBA", thumb.size, (238, 238, 238, 255))
    bg.alpha_composite(thumb)
    im.paste(bg.convert("RGB"), (x + 6, y + 6))
    return True


def _num(v: float | None) -> str:
    """Số đo làm tròn; vắng → `?`."""
    return "?" if v is None else f"{v:.0f}"


def contact_sheet(cards: Sequence[Profile], previews: Mapping[str, bytes]) -> bytes:
    """JPEG lưới ô đánh số 1..n theo thứ tự `cards` (hồ sơ mẫu), ảnh xem trước theo id mẫu.

    Ô không có ảnh xem trước vẽ ô xám; chú thích là số đo, không tên.
    """
    cols = max(1, min(COLS_MAX, len(cards)))
    rows = max(1, (len(cards) + cols - 1) // cols)
    im = Image.new("RGB", (cols * CELL_PX, rows * (CELL_PX + _CAPTION_PX)), "white")
    draw = ImageDraw.Draw(im)
    big, small = load_font(22), load_font(13)
    for i, card in enumerate(cards):
        x, y = (i % cols) * CELL_PX, (i // cols) * (CELL_PX + _CAPTION_PX)
        if not _paste_preview(im, previews.get(card.id), x, y):
            draw.rectangle([x + 6, y + 6, x + CELL_PX - 6, y + CELL_PX - 6], fill=_SWATCH, outline="#999")
        draw.rectangle([x + 6, y + 6, x + 44, y + 38], fill="black")
        draw.text((x + 12, y + 8), str(i + 1), font=big, fill="yellow")
        draw.text((x + 6, y + CELL_PX), f"{card.w:.0f}x{card.d:.0f}x{card.h:.0f} mm", font=small, fill="black")
        facts = f"sáng {_num(card.lightness)} · ấm {_num(card.warmth)} · vân {_num(card.pattern_std)}"
        draw.text((x + 6, y + CELL_PX + 16), facts, font=small, fill="#333")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()
