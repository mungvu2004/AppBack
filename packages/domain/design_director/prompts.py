"""Prompt + JSON schema cho ba lượt Gemini: chọn kiểu, concept (sơn/sàn/mẫu đồ), bổ sung đồ.

Gemini chỉ thấy số ô và số đo, không bao giờ thấy id/tên mẫu; không bao giờ ra toạ độ.
Đổi nội dung prompt/schema → tăng `PROMPT_VERSION` (vào `input_key`, kết quả cũ không dùng lại).
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from packages.domain.design_director.materials import DATA_DIR
from packages.domain.design_director.profiles import Profile
from packages.domain.design_director.styles import STYLE_IDS, STYLES, anchor_text

PROMPT_VERSION: Final = "aid-01.1"
MATERIALS_VERSION: Final = hashlib.sha256(
    b"".join((DATA_DIR / name).read_bytes() for name in ("materials.json", "sheets.json"))
).hexdigest()[:12]
"""Dấu vân của dữ liệu vật liệu (danh sách + thứ tự ô bảng ảnh): sinh lại dữ liệu thì `input_key` đổi."""


def _js(v: object) -> str:
    """JSON gọn, giữ chữ tiếng Việt."""
    return json.dumps(v, ensure_ascii=False)


def _cells(n: int, *, none: bool = False) -> dict[str, Any]:
    """Schema số nguyên enum 1..n (thêm 0 khi `none`)."""
    return {"type": "integer", "enum": ([0] if none else []) + list(range(1, n + 1))}


def pick_style_prompt(rooms: Sequence[Mapping[str, Any]]) -> str:
    """Prompt chọn MỘT phong cách hợp căn; `rooms` = [{usage, areaM2, ...}] mọi tầng. Kèm ảnh mặt bằng sau prompt."""
    lst = {s.id: f"{s.name_vi} ({s.tone}): {s.desc_vi}" for s in STYLES.values()}
    return (
        "Bạn là giám đốc thiết kế nội thất cho nhà ở Việt Nam. Ảnh kèm theo là mặt bằng (chỉ để hiểu bố cục). "
        "Chọn MỘT phong cách nội thất HỢP NHẤT cho cả căn (nhìn bố cục + diện tích/số cửa sổ). "
        "Căn nhỏ/ít cửa sổ thì ưu tiên kiểu sáng. Danh sách:\n"
        + _js(lst)
        + "\nPhòng:\n"
        + _js(list(rooms))
        + "\nTrả styleId (một mã trong danh sách) và reasonVi (1-2 câu, chỉ dựa trên dữ kiện có)."
    )


def pick_style_schema() -> dict[str, Any]:
    """Schema đáp án chọn kiểu: `{styleId: một trong 12 mã, reasonVi}`."""
    return {
        "type": "object",
        "properties": {"styleId": {"type": "string", "enum": list(STYLE_IDS)}, "reasonVi": {"type": "string"}},
        "required": ["styleId", "reasonVi"],
    }


def _profile_facts(n: int, p: Profile) -> dict[str, Any]:
    """Dữ kiện một ô ứng viên (không id, không tên): số ô, cỡ, sáng/ấm, phong cách, chất liệu, mô tả."""
    return {
        "so": n,
        "kichThuocMm": f"{p.w:.0f}x{p.d:.0f}x{p.h:.0f}",
        "sang": p.lightness,
        "am": p.warmth,
        "phongCach": list(p.styles),
        "chatLieu": list(p.materials),
        "moTa": p.desc_vi,
    }


def concept_prompt(
    style_id: str, material_sheets: Mapping[str, int], role_sheets: Mapping[str, Sequence[Profile]]
) -> str:
    """Prompt concept cho `style_id`.

    `material_sheets` = {"paint"|"dry"|"wet": số ô}; `role_sheets` = vai trò → ứng viên theo đúng thứ tự ô
    trên bảng ảnh vai trò đó. Thứ tự ảnh gửi kèm: mặt bằng, bảng "paint", "dry", "wet", rồi từng vai trò.
    """
    facts = {
        "bangVatLieu": dict(material_sheets),
        "bangDo": {role: [_profile_facts(i + 1, p) for i, p in enumerate(ps)] for role, ps in role_sheets.items()},
    }
    return (
        "Bạn là giám đốc thiết kế nội thất cho căn hộ Việt Nam. Ảnh đầu là mặt bằng (chỉ để hiểu bố cục).\n"
        "Các ảnh sau là bảng ứng viên ĐÁNH SỐ; mỗi ô có số đo thật bên dưới (sáng 0-100, ấm >0 là vàng/ấm, "
        "vân = độ tương phản hoa văn). Chỉ dựa vào ảnh và số đo, không đoán theo tên.\n\n"
        f"Phong cách (giữ THỐNG NHẤT cho cả căn): {anchor_text(style_id)}\n\n"
        "Hãy chọn:\n"
        '- wallPaint: số ô trong bảng "paint" cho tường trong chung cả căn.\n'
        '- dryFloor: số ô trong bảng "dry" cho phòng khô (khách, ngủ, hành lang); sàn phải khác rõ độ sáng '
        "với tường.\n"
        '- wetFloor: số ô trong bảng "wet" cho WC, bếp, lô gia.\n'
        "- models: với từng vai trò đồ, số ô trong bảng của vai trò đó; 0 = không cái nào hợp. "
        "Đồ trong cùng căn phải ăn tông với nhau và với sàn/tường.\n"
        "Viết nameVi (≤ 40 ký tự) và summaryVi (2-3 câu, chỉ dựa trên dữ kiện có).\n\n"
        "Dữ kiện:\n" + _js(facts)
    )


def concept_schema(n_paint: int, n_dry: int, n_wet: int, role_counts: Mapping[str, int]) -> dict[str, Any]:
    """Schema concept: số ô enum cho sơn/sàn (1..n) và từng vai trò (0..n, 0 = không cái nào hợp)."""
    models = {role: _cells(n, none=True) for role, n in role_counts.items()}
    return {
        "type": "object",
        "properties": {
            "nameVi": {"type": "string"},
            "summaryVi": {"type": "string"},
            "wallPaint": _cells(n_paint),
            "dryFloor": _cells(n_dry),
            "wetFloor": _cells(n_wet),
            "models": {"type": "object", "properties": models, "required": list(models)},
        },
        "required": ["nameVi", "summaryVi", "wallPaint", "dryFloor", "wetFloor", "models"],
    }


def fill_prompt(edges: Sequence[Mapping[str, Any]]) -> str:
    """Prompt bổ sung đồ thiếu; `edges` = [{edge:"E<n>", room:"R<n>", side, len, doors}].

    Ảnh gửi kèm: 1 = mặt bằng gốc, 2 = sơ đồ máy dựng cùng hướng (phòng R*, cạnh E*, cửa, đồ đã có).
    """
    return (
        "Ảnh 1: mặt bằng gốc của căn hộ (có vẽ ký hiệu đồ đạc: bếp, bồn cầu, lavabo, vòi sen, máy giặt, tủ…).\n"
        "Ảnh 2: sơ đồ CÙNG HƯỚNG do máy dựng: phòng đánh số R0, R1…; mỗi cạnh tường đánh số E1, E2… (chữ đỏ, "
        "nằm phía trong phòng); chấm cam = cửa; khung xám = đồ ĐÃ CÓ. Lưu ý máy có thể gộp nhiều phòng của "
        "bản vẽ gốc thành một phòng.\n\n"
        "Việc của bạn: đề xuất các món CÒN THIẾU để căn hộ trông như nhà thật ở Việt Nam:\n"
        "- Ưu tiên món bản vẽ gốc CÓ VẼ mà sơ đồ chưa có (seenInDrawing=true), đặt đúng phía tường như bản vẽ gốc.\n"
        "- Sau đó là món tối thiểu của nhà thật: WC có bồn cầu + lavabo + vòi sen; bếp có tủ bếp + bếp nấu + "
        "tủ lạnh; lô gia có máy giặt; phòng ngủ có tủ áo; phòng khách có kệ TV (nếu có TV).\n"
        "- Không thêm món đã có. Không chọn cạnh có cửa nếu món che cửa. Mỗi món: roomRef = phòng, "
        "edgeRef = cạnh tường của phòng đó để món dựa vào, pos = vị trí dọc cạnh: 0 = đầu trái/trên, "
        "1 = đầu phải/dưới, 0.5 = giữa.\n\n"
        "Danh sách cạnh (side = phía của tường trong phòng; len mm; doors = cửa trên cạnh):\n" + _js(list(edges))
    )


def fill_schema(item_types: Sequence[str], room_refs: Sequence[str], edge_refs: Sequence[str]) -> dict[str, Any]:
    """Schema bổ sung đồ: tối đa 20 món {type enum, roomRef "R<n>", edgeRef "E<n>", pos 0-1, ...}."""
    item = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": sorted(item_types)},
            "roomRef": {"type": "string", "enum": list(room_refs)},
            "edgeRef": {"type": "string", "enum": list(edge_refs)},
            "pos": {"type": "number", "minimum": 0, "maximum": 1},
            "seenInDrawing": {"type": "boolean"},
            "reasonVi": {"type": "string"},
        },
        "required": ["type", "roomRef", "edgeRef", "pos", "seenInDrawing", "reasonVi"],
    }
    return {
        "type": "object",
        "properties": {"additions": {"type": "array", "maxItems": 20, "items": item}},
        "required": ["additions"],
    }
