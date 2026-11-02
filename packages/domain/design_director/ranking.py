"""Xếp hạng mẫu đồ ứng viên cho một vai trò + phong cách (lọc cứng, chấm điểm, bỏ trùng nhóm)."""

from collections.abc import Iterable
from typing import Final

from packages.domain.design_director.profiles import Profile
from packages.domain.design_director.roles import MAIN_ROLES, ROLE_TYPE, TYPICAL_SIZE_MM
from packages.domain.design_director.styles import STYLES, Tone

SIZE_TOL: Final = 0.30
MAIN_LIMIT: Final = 12
MINOR_LIMIT: Final = 4
STYLE_BONUS: Final = 1000.0

# Đích (độ sáng L, độ ấm b*) theo nhóm tông khi không có gợi ý bảng màu.
TONE_TARGET: Final[dict[Tone, tuple[float, float]]] = {
    "sáng-ấm": (70.0, 12.0),
    "sáng-lạnh": (75.0, 2.0),
    "trầm-ấm": (45.0, 15.0),
    "tối-lạnh": (35.0, 3.0),
}


def fits_size(p: Profile, size_mm: tuple[float, float], tol: float = SIZE_TOL) -> bool:
    """Đúng khi (w, d) của mẫu lệch ≤ tol so với `size_mm`, cho phép xoay 90°."""
    w, d = size_mm

    def ok(a: float, b: float) -> bool:
        """|a - b| ≤ tol·b."""
        return abs(a - b) <= tol * max(b, 1.0)

    return (ok(p.w, w) and ok(p.d, d)) or (ok(p.w, d) and ok(p.d, w))


def _score(p: Profile, style_id: str, target: tuple[float, float]) -> float:
    """Điểm: khớp phong cách trước (mã đầu danh sách được thêm), rồi gần (L, b*) đích; thiếu số đo = phạt 100."""
    style = STYLE_BONUS if style_id in p.styles else 0.0
    if p.styles and p.styles[0] == style_id:
        style += 1.0
    if p.lightness is None or p.warmth is None:
        return style - 100.0
    return style - (abs(p.lightness - target[0]) + abs(p.warmth - target[1]))


def rank_candidates(
    profiles: Iterable[Profile],
    role: str,
    style_id: str,
    palette_hint: tuple[float, float, float] | None = None,
    limit: int | None = None,
    *,
    size_mm: tuple[float, float] | None = None,
) -> tuple[Profile, ...]:
    """Ứng viên tốt nhất cho `role` theo `style_id`.

    Lọc cứng: đúng `type` của vai trò, cỡ ±30 % (xoay được) so với `size_mm` hoặc cỡ điển hình, có license,
    `qc.ok`. Điểm: phong cách rồi độ hợp màu với `palette_hint` (Lab; dùng L và b*) hoặc đích của nhóm tông.
    Cùng `dupGroup` chỉ giữ mẫu điểm cao nhất. Hoà điểm xếp theo id. `limit` mặc định 12 món chính, 4 món phụ.
    Vai trò hoặc phong cách lạ → `KeyError`.
    """
    typ = ROLE_TYPE[role]
    tone = STYLES[style_id].tone
    target = (palette_hint[0], palette_hint[2]) if palette_hint else TONE_TARGET[tone]
    size = size_mm or TYPICAL_SIZE_MM[role]
    ok = [p for p in profiles if p.type == typ and p.license and p.qc_ok and fits_size(p, size)]
    ok.sort(key=lambda p: (-_score(p, style_id, target), p.id))
    seen: set[str] = set()
    out: list[Profile] = []
    for p in ok:
        if p.dup_group:
            if p.dup_group in seen:
                continue
            seen.add(p.dup_group)
        out.append(p)
    n = limit if limit is not None else (MAIN_LIMIT if role in MAIN_ROLES else MINOR_LIMIT)
    return tuple(out[:n])
