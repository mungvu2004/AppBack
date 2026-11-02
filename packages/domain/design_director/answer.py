"""Kiểm đáp án concept của Gemini và đổi số ô → `DesignResult` (chưa có `additions`, agent W thêm)."""

from collections.abc import Mapping, Sequence
from typing import Any, Final

from packages.domain.design_director.materials import Material, MaterialSets
from packages.domain.design_director.styles import STYLES

MIN_FLOOR_WALL_DELTA_L: Final = 8.0
NAME_MAX: Final = 40


def _cell(answer: Mapping[str, Any], key: str, cells: Sequence[Material], errors: list[str]) -> Material | None:
    """Vật liệu ở ô `answer[key]` (1..n); sai kiểu/ngoài khoảng → ghi lỗi, trả None."""
    v = answer.get(key)
    if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= len(cells):
        errors.append(f"{key}={v!r} ngoài khoảng 1..{len(cells)}")
        return None
    return cells[v - 1]


def _models(answer: Mapping[str, Any], role_cells: Mapping[str, Sequence[str]], errors: list[str]) -> dict[str, str]:
    """Vai trò → id mẫu theo số ô (0 = bỏ qua); vai trò lạ hoặc số ngoài khoảng → ghi lỗi."""
    raw = answer.get("models", {})
    if not isinstance(raw, Mapping):
        errors.append("models không phải object")
        return {}
    out: dict[str, str] = {}
    for role, v in raw.items():
        cells = role_cells.get(role)
        if cells is None:
            errors.append(f"models.{role}: vai trò không có bảng")
        elif isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= len(cells):
            errors.append(f"models.{role}={v!r} ngoài khoảng 0..{len(cells)}")
        elif v:
            out[role] = cells[v - 1]
    return out


def _text(v: object, fallback: str) -> str:
    """Chuỗi đã cắt khoảng trắng hoặc `fallback` khi rỗng/không phải chuỗi."""
    return v.strip() if isinstance(v, str) and v.strip() else fallback


def to_result(
    answer: Mapping[str, Any],
    sets: MaterialSets,
    role_cells: Mapping[str, Sequence[str]],
    style_id: str,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Đổi đáp án concept → (`DesignResult` dict trừ `additions`, lỗi). Có lỗi → (None, lỗi).

    `role_cells` = vai trò → id mẫu theo thứ tự ô bảng ảnh. Luật: số ô trong khoảng; sàn khô thuộc tập khô;
    |L(sàn khô) - L(tường)| ≥ 8. Sàn khô → `wood`, sàn ướt → `tile` + `mosaic`.
    """
    style = STYLES[style_id]
    errors: list[str] = []
    wall = _cell(answer, "wallPaint", sets.paint, errors)
    dry = _cell(answer, "dryFloor", sets.dry, errors)
    wet = _cell(answer, "wetFloor", sets.wet, errors)
    models = _models(answer, role_cells, errors)
    if wall is not None and dry is not None and abs(dry.lightness - wall.lightness) < MIN_FLOOR_WALL_DELTA_L:
        errors.append(f"sàn và tường gần trùng độ sáng (ΔL={abs(dry.lightness - wall.lightness):.0f} < 8)")
    if errors or wall is None or dry is None or wet is None:
        return None, tuple(errors)
    return {
        "nameVi": _text(answer.get("nameVi"), style.name_vi)[:NAME_MAX],
        "summaryVi": _text(answer.get("summaryVi"), ""),
        "baseStyle": style.base_style,
        "wall": {"interior": wall.ref},
        "floor": {"wood": dry.ref, "tile": wet.ref, "mosaic": wet.ref},
        "models": models,
    }, ()
