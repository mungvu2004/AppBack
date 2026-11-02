"""Nạp dữ liệu vật liệu tĩnh (`data/`, sinh bởi `tools/design_director/build_materials.py`)."""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final, Literal

DATA_DIR: Final = Path(__file__).with_name("data")
SetName = Literal["paint", "dry", "wet"]
SET_NAMES: Final[tuple[SetName, ...]] = ("paint", "dry", "wet")


@dataclass(frozen=True)
class Material:
    """Một vật liệu thư viện Pascal kèm số đo màu (Lab trung bình, sáng, ấm, rực, vân)."""

    id: str
    ref: str
    category: str
    surfaces: tuple[str, ...]
    lab: tuple[float, float, float]
    lightness: float
    warmth: float
    chroma: float
    pattern: float


@dataclass(frozen=True)
class MaterialSets:
    """Ba tập theo thứ tự ô của bảng ảnh: ô số n = phần tử n-1."""

    paint: tuple[Material, ...]
    dry: tuple[Material, ...]
    wet: tuple[Material, ...]


def _material(raw: dict[str, Any]) -> Material:
    """Dựng `Material` từ một bản ghi `materials.json`."""
    lab = raw["lab"]
    return Material(
        id=str(raw["id"]),
        ref=str(raw["ref"]),
        category=str(raw["category"]),
        surfaces=tuple(str(s) for s in raw["surfaces"]),
        lab=(float(lab[0]), float(lab[1]), float(lab[2])),
        lightness=float(raw["lightness"]),
        warmth=float(raw["warmth"]),
        chroma=float(raw["chroma"]),
        pattern=float(raw["pattern"]),
    )


@cache
def load_materials() -> tuple[Material, ...]:
    """Mọi vật liệu trong `materials.json`."""
    raw = json.loads((DATA_DIR / "materials.json").read_text(encoding="utf-8"))
    return tuple(_material(r) for r in raw)


@cache
def material_sets() -> MaterialSets:
    """Ba tập sơn / sàn khô / sàn ướt theo `sheets.json` (đúng thứ tự số ô trên bảng ảnh)."""
    by_id = {m.id: m for m in load_materials()}
    raw = json.loads((DATA_DIR / "sheets.json").read_text(encoding="utf-8"))
    paint, dry, wet = (tuple(by_id[i] for i in raw[name]) for name in SET_NAMES)
    return MaterialSets(paint, dry, wet)


def sheet_jpeg(name: SetName) -> bytes:
    """Bytes JPEG của bảng ảnh đánh số `sheet-<name>.jpg`."""
    return (DATA_DIR / f"sheet-{name}.jpg").read_bytes()
