"""Công cụ sinh dữ liệu vật liệu (AID-01): đọc thư viện Pascal giả trong thư mục tạm, không đụng `data/` thật."""

import json
from pathlib import Path

import pytest
from PIL import Image, ImageFont

from tools.design_director import build_materials as bm

LIBRARY = """export const MATERIALS = [
  {
    id: 'paint-cream',
    category: 'colors',
    surfaces: ['wall'],
    previewColor: '#f0e6d2',
  },
  {
    id: 'wood-oak',
    category: 'wood',
    surfaces: ['floor', 'wall'],
    previewThumbnailUrl: '/material/wood/oak_thumb.png',
  },
  {
    id: 'tile-flower',
    category: 'tile',
    surfaces: ['floor'],
    previewThumbnailUrl: '/material/tile/flower_thumb.png',
  },
  {
    id: 'lost-thumb',
    category: 'wood',
    surfaces: ['floor'],
    previewThumbnailUrl: '/material/wood/missing.png',
  },
  {
    id: 'no-look',
    category: 'stone',
  },
  {
    id: 'no-category',
    previewColor: '#000000',
  },
]
"""


def _fe(tmp_path: Path) -> Path:
    """Gốc AppFront giả: tệp thư viện + hai ảnh (gỗ trơn, gạch kẻ ô đậm)."""
    fe = tmp_path / "fe"
    src = fe / "vendor/pascal/packages/core/src"
    src.mkdir(parents=True)
    (src / "material-library.ts").write_text(LIBRARY, encoding="utf-8")
    pics = fe / "public/pascal/material"
    (pics / "wood").mkdir(parents=True)
    (pics / "tile").mkdir(parents=True)
    Image.new("RGB", (32, 32), (170, 120, 70)).save(pics / "wood/oak_thumb.png")
    tile = Image.new("RGB", (32, 32), "white")
    for x in range(0, 32, 4):
        for y in range(0, 32, 4):
            if (x + y) % 8 == 0:
                tile.paste((10, 10, 10), (x, y, x + 4, y + 4))
    tile.save(pics / "tile/flower_thumb.png")
    return fe


def test_materials_skip_unusable_blocks_and_split_sets(tmp_path: Path) -> None:
    """Bỏ khối thiếu loại, thiếu ảnh/màu, ảnh mất; gạch vân đậm chỉ vào tập ướt."""
    cards, looks = bm.materials(_fe(tmp_path))
    assert [c["id"] for c in cards] == ["paint-cream", "wood-oak", "tile-flower"]
    assert looks["paint-cream"] == "#F0E6D2"
    assert cards[2]["pattern"] > bm.DRY_PATTERN_MAX >= cards[1]["pattern"]
    assert bm.split_sets(cards) == {"paint": ["paint-cream"], "dry": ["wood-oak"], "wet": ["tile-flower"]}


def test_main_writes_data_and_sheets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ghi đủ 5 tệp; font có thật thì dùng (giả bằng phông mặc định), JPEG lớn thì tự thu nhỏ."""
    default = ImageFont.load_default()  # nạp trước: `load_default` tự gọi `truetype`
    monkeypatch.setattr(ImageFont, "truetype", lambda *_a, **_k: default)
    monkeypatch.setattr(bm, "MAX_JPG", 2_000)
    out = tmp_path / "out"
    assert bm.main([str(_fe(tmp_path)), "font.ttf"], out=out) == 0
    assert json.loads((out / "sheets.json").read_text(encoding="utf-8"))["wet"] == ["tile-flower"]
    assert len(json.loads((out / "materials.json").read_text(encoding="utf-8"))) == 3
    for name in ("paint", "dry", "wet"):
        assert 0 < (out / f"sheet-{name}.jpg").stat().st_size < 2_000


def test_sheet_falls_back_to_default_font(tmp_path: Path) -> None:
    """Không có phông `.ttf` → phông mặc định của Pillow, vẫn vẽ được ô màu."""
    cards, looks = bm.materials(_fe(tmp_path))
    im = bm.sheet(cards[:1], looks, str(tmp_path / "no-such-font.ttf"))
    assert im.size == (220, 266)
