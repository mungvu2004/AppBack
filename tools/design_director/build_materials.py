"""Sinh dữ liệu vật liệu tĩnh cho `packages/domain/design_director/data/` (chạy tay, kết quả commit).

Đọc `vendor/pascal/packages/core/src/material-library.ts` + ảnh `public/pascal/...` của AppFront, đo màu Lab,
chia ba tập (sơn, sàn khô, sàn ướt) theo luật hợp đồng AID-01 và vẽ bảng ảnh đánh số (không tên, không id).
Không chạy trong cổng: cần Pillow + numpy trên máy chủ. Chạy:
    python -X utf8 tools/design_director/build_materials.py F:/App/AppFront [đường-font.ttf]
"""

import io
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[2] / "packages/domain/design_director/data"
MAX_JPG = 400_000
DRY_CATEGORIES = ("wood", "tile", "stone", "concrete")
WET_CATEGORIES = ("tile", "stone")
DRY_PATTERN_MAX = 10


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Đổi mảng RGB 0-255 (Nx3) sang CIE Lab (D65)."""
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = c @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], 1)


def describe(pixels: np.ndarray) -> dict[str, Any]:
    """Số đo của một ảnh: Lab trung bình, độ sáng, độ ấm (b*), độ rực, độ vân (độ lệch chuẩn L)."""
    lab = srgb_to_lab(pixels.astype(float))
    mean = lab.mean(0)
    return {
        "lab": [round(float(v), 1) for v in mean],
        "lightness": round(float(mean[0])),
        "warmth": round(float(mean[2])),
        "chroma": round(float(np.hypot(lab[:, 1], lab[:, 2]).mean())),
        "pattern": round(float(lab[:, 0].std())),
    }


def materials(fe: Path) -> tuple[list[dict[str, Any]], dict[str, str | None]]:
    """Đọc thư viện vật liệu Pascal → (thẻ vật liệu, id → đường ảnh hoặc màu hex cho bảng ảnh)."""
    src = (fe / "vendor/pascal/packages/core/src/material-library.ts").read_text(encoding="utf-8")
    cards: list[dict[str, Any]] = []
    looks: dict[str, str | None] = {}
    for blk in re.split(r"\n  \{\n    id: '", src)[1:]:
        mid = blk.split("'", 1)[0]
        cat = re.search(r"category: '([^']+)'", blk)
        surf = re.search(r"surfaces: \[([^\]]*)\]", blk)
        thumb = re.search(r"previewThumbnailUrl: '([^']+)'", blk)
        colour = re.search(r"previewColor: '(#[0-9a-fA-F]{6})'", blk)
        if cat is None:
            continue
        if thumb:
            path = fe / "public/pascal" / thumb.group(1).lstrip("/")
            if not path.exists():
                continue
            px = np.asarray(Image.open(path).convert("RGB")).reshape(-1, 3)
            looks[mid] = str(path)
        elif colour:
            h = colour.group(1)
            px = np.array([[int(h[i : i + 2], 16) for i in (1, 3, 5)]] * 4)
            looks[mid] = h.upper()
        else:
            continue
        cards.append(
            {
                "id": mid,
                "ref": f"library:{mid}",
                "category": cat.group(1),
                "surfaces": re.findall(r"'(\w+)'", surf.group(1)) if surf else [],
                **describe(px),
            }
        )
    return cards, looks


def split_sets(cards: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Ba tập theo luật hợp đồng: sơn = colors; khô = sàn gỗ/gạch/đá/bê tông vân ≤ 10; ướt = sàn gạch/đá."""
    floor = [c for c in cards if "floor" in c["surfaces"]]
    return {
        "paint": [c["id"] for c in cards if c["category"] == "colors"],
        "dry": [c["id"] for c in floor if c["category"] in DRY_CATEGORIES and c["pattern"] <= DRY_PATTERN_MAX],
        "wet": [c["id"] for c in floor if c["category"] in WET_CATEGORIES],
    }


def sheet(cards: list[dict[str, Any]], looks: dict[str, str | None], font_path: str | None) -> Image.Image:
    """Bảng ảnh đánh số như bản thử (`facts.sheet`): ảnh/mẫu màu + số đo, không tên."""
    try:
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.truetype(font_path or "arial.ttf", 13)
        big: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.truetype(font_path or "arialbd.ttf", 26)
    except OSError:
        font = big = ImageFont.load_default()
    cell, cols = 220, min(6, len(cards))
    rows = (len(cards) + cols - 1) // cols
    im = Image.new("RGB", (cols * cell, rows * (cell + 46)), "white")
    d = ImageDraw.Draw(im)
    for i, c in enumerate(cards):
        x, y = (i % cols) * cell, (i // cols) * (cell + 46)
        look = looks[c["id"]]
        if look and not look.startswith("#"):
            t = Image.open(look).convert("RGBA")
            t.thumbnail((cell - 12, cell - 12))
            bg = Image.new("RGBA", t.size, (238, 238, 238, 255))
            bg.alpha_composite(t)
            im.paste(bg.convert("RGB"), (x + 6, y + 6))
        else:
            d.rectangle([x + 6, y + 6, x + cell - 6, y + cell - 6], fill=look, outline="#999")
        d.rectangle([x + 6, y + 6, x + 44, y + 38], fill="black")
        d.text((x + 12, y + 8), str(i + 1), font=big, fill="yellow")
        d.text((x + 6, y + cell), c["category"], font=font, fill="black")
        d.text(
            (x + 6, y + cell + 16),
            f"sáng {c['lightness']} · ấm {c['warmth']} · vân {c['pattern']}",
            font=font,
            fill="#333",
        )
    return im


def save_jpg(im: Image.Image, path: Path) -> int:
    """Lưu JPEG, hạ chất lượng (rồi cỡ) tới khi < 400 KB; trả số byte."""
    while True:
        for q in (88, 80, 72, 64, 56):
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=q, optimize=True)
            if buf.tell() < MAX_JPG:
                path.write_bytes(buf.getvalue())
                return buf.tell()
        im = im.resize((im.width * 4 // 5, im.height * 4 // 5))


def main(argv: list[str]) -> int:
    """Điểm vào: argv = [gốc AppFront, font .ttf tuỳ chọn]."""
    fe = Path(argv[0])
    font_path = argv[1] if len(argv) > 1 else None
    cards, looks = materials(fe)
    sets = split_sets(cards)
    by_id = {c["id"]: c for c in cards}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "materials.json").write_text(json.dumps(cards, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (OUT / "sheets.json").write_text(json.dumps(sets, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, ids in sets.items():
        size = save_jpg(sheet([by_id[i] for i in ids], looks, font_path), OUT / f"sheet-{name}.jpg")
        sys.stdout.write(f"{name}: {len(ids)} ô, {size} B\n")
    sys.stdout.write(f"{len(cards)} vật liệu\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
