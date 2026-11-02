"""Đọc hồ sơ mẫu đồ (`profiles.jsonl` của phiên thư viện) → `Profile`; dòng hỏng bị bỏ kèm lý do."""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileColor:
    """Một màu chủ đạo của mẫu: Lab, tỉ lệ diện tích, hex."""

    lab: tuple[float, float, float]
    share: float
    hex: str


@dataclass(frozen=True)
class Profile:
    """Hồ sơ một mẫu: kích thước mm (w=X, d=Z, h=Y), màu đo, loại, phong cách, giấy phép, QC."""

    id: str
    w: float
    d: float
    h: float
    type: str
    colors: tuple[ProfileColor, ...] = ()
    lightness: float | None = None
    warmth: float | None = None
    chroma: float | None = None
    pattern_std: float | None = None
    type_detail: str | None = None
    styles: tuple[str, ...] = ()
    materials: tuple[str, ...] = ()
    desc_vi: str | None = None
    dup_group: str | None = None
    license: str | None = None
    qc_ok: bool = False
    qc_issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedProfiles:
    """Kết quả đọc: hồ sơ hợp lệ + lý do từng dòng bị bỏ ("dòng <n>: <lý do>")."""

    profiles: tuple[Profile, ...]
    skipped: tuple[str, ...]


def _num(v: object) -> float | None:
    """Số thực từ giá trị JSON (bool không tính); khác → None."""
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None


def _strs(v: object) -> tuple[str, ...]:
    """Tuple chuỗi từ list JSON; phần tử không phải chuỗi bị bỏ."""
    return tuple(x for x in v if isinstance(x, str)) if isinstance(v, list) else ()


def _opt_str(v: object) -> str | None:
    """Chuỗi khác rỗng hoặc None."""
    return v if isinstance(v, str) and v else None


def _color(v: object) -> ProfileColor | None:
    """Một màu `{lab:[L,a,b], share, hex}`; sai dạng → None."""
    if not isinstance(v, Mapping):
        return None
    lab, share = v.get("lab"), _num(v.get("share"))
    nums = [_num(x) for x in lab] if isinstance(lab, list) and len(lab) == 3 else []
    if len(nums) != 3 or share is None:
        return None
    l_, a, b = nums
    if l_ is None or a is None or b is None:
        return None
    return ProfileColor((l_, a, b), share, str(v.get("hex", "")))


def _size(v: object) -> tuple[float, float, float]:
    """Kích thước `{w,d,h}` mm, mỗi giá trị dương; sai → `ValueError`."""
    if not isinstance(v, Mapping):
        raise ValueError("sizeMm sai")
    w, d, h = (_num(v.get(k)) for k in ("w", "d", "h"))
    if w is None or d is None or h is None or min(w, d, h) <= 0:
        raise ValueError("sizeMm sai")
    return w, d, h


def parse_profile(raw: object) -> Profile:
    """Dựng `Profile` từ một bản ghi JSON; thiếu id/type/kích thước dương → `ValueError`. Trường lạ bị lờ."""
    if not isinstance(raw, Mapping):
        raise ValueError("không phải object")
    pid, typ = raw.get("id"), raw.get("type")
    if not isinstance(pid, str) or not pid:
        raise ValueError("thiếu id")
    if not isinstance(typ, str) or not typ:
        raise ValueError("thiếu type")
    w, d, h = _size(raw.get("sizeMm"))
    qc = raw.get("qc")
    qc_map: Mapping[str, object] = qc if isinstance(qc, Mapping) else {}
    colors = raw.get("colors")
    return Profile(
        id=pid,
        w=w,
        d=d,
        h=h,
        type=typ,
        colors=tuple(c for c in (_color(x) for x in (colors if isinstance(colors, list) else [])) if c),
        lightness=_num(raw.get("lightness")),
        warmth=_num(raw.get("warmth")),
        chroma=_num(raw.get("chroma")),
        pattern_std=_num(raw.get("patternStd")),
        type_detail=_opt_str(raw.get("typeDetail")),
        styles=_strs(raw.get("styles")),
        materials=_strs(raw.get("materials")),
        desc_vi=_opt_str(raw.get("descVi")),
        dup_group=_opt_str(raw.get("dupGroup")),
        license=_opt_str(raw.get("license")),
        qc_ok=qc_map.get("ok") is True,
        qc_issues=_strs(qc_map.get("issues")),
    )


def parse_profiles(lines: Iterable[str]) -> ParsedProfiles:
    """Đọc các dòng jsonl; dòng trống bị bỏ im, dòng hỏng bị bỏ kèm lý do; id trùng giữ dòng đầu."""
    out: dict[str, Profile] = {}
    skipped: list[str] = []
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            p = parse_profile(json.loads(line))
        except ValueError as e:  # json.JSONDecodeError cũng là ValueError
            skipped.append(f"dòng {n}: {e}")
            continue
        if p.id in out:
            skipped.append(f"dòng {n}: id trùng {p.id}")
            continue
        out[p.id] = p
    return ParsedProfiles(tuple(out.values()), tuple(skipped))
