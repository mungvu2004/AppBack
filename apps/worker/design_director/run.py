"""Điều phối một lượt AID-01: (chọn kiểu) → concept → kiểm (thử lại 1 lần) → bổ sung đồ → đặt bằng mã.

Gemini chỉ thấy số ô + số đo (`packages.domain.design_director.prompts`), mã ở đây đổi số → id thật
(`answer.to_result`) và tự đặt đồ (`fill.place_additions`). Cổng `GenAI` nhận qua tham số để test
tiêm `FakeGenAI`; `tasks.py` nối bản thật và bộ nạp.
"""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, NamedTuple

from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.design_director.state import (
    DESIGN_DIRECTOR_FAILED,
    DESIGN_DIRECTOR_OUTPUT_INVALID,
    claim,
    fail,
    finish,
)
from apps.worker.design_director.fill import ADD, edge_summary, edges_of, label_rooms, place_additions, schematic
from apps.worker.design_director.sheets import contact_sheet
from packages.db.engine import session_scope
from packages.domain.design_director.answer import to_result
from packages.domain.design_director.materials import SET_NAMES, material_sets, sheet_jpeg
from packages.domain.design_director.profiles import Profile
from packages.domain.design_director.prompts import (
    concept_prompt,
    concept_schema,
    fill_prompt,
    fill_schema,
    pick_style_prompt,
    pick_style_schema,
)
from packages.domain.design_director.ranking import rank_candidates
from packages.domain.design_director.roles import roles_for_usages
from packages.domain.design_director.styles import STYLE_IDS
from packages.domain.spatial.model import SpatialLayer
from packages.genai import GenAI, GenAIError, ImagePart, Part, TextPart

__all__ = [
    "DesignDirectorError",
    "DesignInputs",
    "LevelInput",
    "Loader",
    "RunOutput",
    "direct_concept",
    "run_concept",
    "to_jpeg",
]

_log: Final = logging.getLogger(__name__)

PAGE_MAX_SIDE: Final = 1600

Json = Mapping[str, Any]


class DesignDirectorError(Exception):
    """Lượt hỏng có mã (`DESIGN_DIRECTOR_FAILED` | `DESIGN_DIRECTOR_OUTPUT_INVALID`)."""

    def __init__(self, code: str) -> None:
        """Giữ mã để `fail` ghi."""
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class LevelInput:
    """Một tầng: tài liệu không gian + ảnh trang bản vẽ gốc (có thể vắng)."""

    level_id: str
    name: str
    layer: SpatialLayer
    page_image: bytes | None = None


@dataclass(frozen=True, slots=True)
class DesignInputs:
    """Đầu vào đã nạp của một lượt: mọi tầng, hồ sơ mẫu đã publish, ảnh xem trước theo id mẫu."""

    project_id: str
    style_id: str | None
    levels: tuple[LevelInput, ...]
    profiles: tuple[Profile, ...] = ()
    previews: Mapping[str, bytes] = field(default_factory=dict)


class RunOutput(NamedTuple):
    """Kết quả một lượt: `DesignResult` (có `additions`), `usage`, mã kiểu đã dùng."""

    result: dict[str, Any]
    usage: dict[str, Any]
    style_id: str


def to_jpeg(data: bytes, max_side: int = PAGE_MAX_SIDE) -> bytes | None:
    """Thu ảnh về cạnh dài ≤ `max_side`, JPEG 88; ảnh hỏng → `None`."""
    try:
        im = Image.open(io.BytesIO(data)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        return None
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


class _Caller:
    """Gọi `GenAI` và cộng dồn `usage`; `GenAIError` → `DESIGN_DIRECTOR_FAILED`."""

    def __init__(self, genai: GenAI) -> None:
        """Bắt đầu `usage` bằng 0."""
        self.genai = genai
        self.usage: dict[str, Any] = {"inputTokens": 0, "outputTokens": 0, "calls": 0, "seconds": 0.0}

    def __call__(self, parts: Sequence[Part], schema: Json) -> Json:
        """Một lượt `generate_json`."""
        try:
            res = self.genai.generate_json(parts, schema, thinking="low")
        except GenAIError as exc:
            _log.warning("design_director_ai_error", extra={"code": exc.code})
            raise DesignDirectorError(DESIGN_DIRECTOR_FAILED) from None
        self.usage["calls"] += 1
        self.usage["inputTokens"] += res.input_tokens
        self.usage["outputTokens"] += res.output_tokens
        self.usage["seconds"] = round(self.usage["seconds"] + res.seconds, 3)
        return res.data


def _page(level: LevelInput) -> bytes | None:
    """Ảnh trang gốc của tầng đã thu nhỏ; vắng/hỏng → `None`."""
    return to_jpeg(level.page_image) if level.page_image else None


def _page_parts(inputs: DesignInputs) -> list[Part]:
    """Ảnh trang gốc của từng tầng, mỗi ảnh có dòng chú thích tên tầng."""
    parts: list[Part] = []
    for level in inputs.levels:
        if (jpeg := _page(level)) is not None:
            parts += [TextPart(f"Ảnh mặt bằng {level.name}:"), ImagePart(jpeg, "image/jpeg")]
    return parts


def _pick_style(call: _Caller, inputs: DesignInputs, pages: list[Part]) -> str:
    """Lượt AI tự chọn kiểu cho cả căn; mã lạ → `DESIGN_DIRECTOR_OUTPUT_INVALID`."""
    rooms = [
        {"tang": lv.name, "usage": r.usage, "areaM2": round(float(r.area_m2), 1)}
        for lv in inputs.levels
        for r in lv.layer.rooms
    ]
    style_id = call([TextPart(pick_style_prompt(rooms)), *pages], pick_style_schema()).get("styleId")
    if style_id not in STYLE_IDS:
        raise DesignDirectorError(DESIGN_DIRECTOR_OUTPUT_INVALID)
    return str(style_id)


def _model_for(kind: str, result: Json, profiles: Sequence[Profile]) -> Profile | None:
    """Mẫu cho món bổ sung: mẫu AI đã chọn cùng loại nếu có, không thì mẫu gọn nhất cùng loại."""
    same = [p for p in profiles if p.type == kind]
    chosen = set(result.get("models", {}).values())
    picked = [p for p in same if p.id in chosen]
    if picked:
        return picked[0]
    return min(same, key=lambda p: (p.w * p.d, p.id), default=None)


def _additions(call: _Caller, inputs: DesignInputs, result: Json) -> list[dict[str, Any]]:
    """Lượt bổ sung đồ: sơ đồ R*/E* mỗi tầng → AI chọn món + cạnh + vị trí → mã đặt. Không cạnh → `[]`."""
    labels = label_rooms([r for lv in inputs.levels for r in lv.layer.rooms])
    per_level = [
        (lv, [edges_of(r, labels[r.id], lv.layer.openings, lv.layer.walls) for r in lv.layer.rooms])
        for lv in inputs.levels
    ]
    rooms = [r for _, rs in per_level for r in rs]
    edges = [e.id for r in rooms for e in r.edges]
    if not edges:
        return []
    schema = fill_schema(sorted(ADD), [r.label for r in rooms], edges)
    parts: list[Part] = [TextPart(fill_prompt(edge_summary(rooms)))]
    for lv, rs in per_level:
        if not rs:
            continue
        if (jpeg := _page(lv)) is not None:
            parts += [TextPart(f"{lv.name}, bản vẽ gốc:"), ImagePart(jpeg, "image/jpeg")]
        sketch = schematic(rs, lv.layer.furniture)
        parts += [TextPart(f"{lv.name}, sơ đồ đánh số:"), ImagePart(sketch, "image/png")]
    answers = []
    for ans in call(parts, schema).get("additions") or []:
        if not isinstance(ans, Mapping):
            continue
        model = _model_for(str(ans.get("type")), result, inputs.profiles)
        answers.append(
            {
                "type": ans.get("type"),
                "edge": ans.get("edgeRef"),
                "pos": ans.get("pos", 0.5),
                "widthMm": model.w if model else None,
                "depthMm": model.d if model else None,
                "modelId": model.id if model else None,
            }
        )
    return place_additions(rooms, [f for lv in inputs.levels for f in lv.layer.furniture], answers)


def run_concept(inputs: DesignInputs, genai: GenAI) -> RunOutput:
    """Một lượt đầy đủ (chặn, gọi trong luồng phụ); hỏng → `DesignDirectorError` có mã.

    Đáp án concept sai → gọi lại một lần kèm danh sách lỗi; lượt bổ sung đồ hỏng chỉ bỏ `additions`.
    """
    call = _Caller(genai)
    pages = _page_parts(inputs)
    style_id = inputs.style_id or _pick_style(call, inputs, pages)
    usages = [r.usage for lv in inputs.levels for r in lv.layer.rooms]
    cards = {role: c for role in roles_for_usages(usages) if (c := rank_candidates(inputs.profiles, role, style_id))}
    sets = material_sets()
    prompt = concept_prompt(style_id, {name: len(getattr(sets, name)) for name in SET_NAMES}, cards)
    schema = concept_schema(len(sets.paint), len(sets.dry), len(sets.wet), {r: len(c) for r, c in cards.items()})
    parts: list[Part] = [TextPart(prompt), *pages]
    for name in SET_NAMES:
        parts += [TextPart(f'Bảng "{name}":'), ImagePart(sheet_jpeg(name), "image/jpeg")]
    for role, role_cards in cards.items():
        parts += [TextPart(f'Bảng "{role}":'), ImagePart(contact_sheet(role_cards, inputs.previews), "image/jpeg")]
    role_cells = {role: [p.id for p in c] for role, c in cards.items()}
    result, errors = to_result(call(parts, schema), sets, role_cells, style_id)
    if result is None:
        feedback = "Câu trả lời trước không hợp lệ: " + "; ".join(errors) + ". Hãy chọn lại, sửa đúng các lỗi này."
        result, errors = to_result(call([*parts, TextPart(feedback)], schema), sets, role_cells, style_id)
        if result is None:
            _log.warning("design_director_invalid", extra={"errors": list(errors)})
            raise DesignDirectorError(DESIGN_DIRECTOR_OUTPUT_INVALID)
    try:
        result["additions"] = _additions(call, inputs, result)
    except DesignDirectorError:
        _log.warning("design_director_fill_failed", extra={"project_id": inputs.project_id})
        result["additions"] = []
    return RunOutput(result, call.usage, style_id)


Loader = Callable[[str, str | None], Awaitable[DesignInputs]]
"""`(project_id, style_id)` → đầu vào đã nạp (DB + kho, session ngắn của riêng nó)."""


async def direct_concept(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    concept_id: str,
    load: Loader,
    genai: GenAI | None,
) -> None:
    """Lõi task: `claim` (None = giao lặp, no-op) → nạp → chạy → `finish`; lỗi có mã → `fail`.

    Không có cổng AI (thiếu khoá) → `DESIGN_DIRECTOR_FAILED`. Lỗi khác (DB, kho…) ném ra để
    `define_task` thử lại rồi gọi `on_failed`. Không giữ session khi gọi AI (K22).
    """
    async with session_scope(sessionmaker) as db:
        claimed = await claim(db, concept_id)
    if claimed is None:
        _log.info("design_director_not_claimable", extra={"concept_id": concept_id})
        return
    try:
        if genai is None:
            raise DesignDirectorError(DESIGN_DIRECTOR_FAILED)
        inputs = await load(claimed.project_id, claimed.style_id)
        out = await asyncio.to_thread(run_concept, inputs, genai)
    except DesignDirectorError as exc:
        async with session_scope(sessionmaker) as db:
            await fail(db, concept_id, exc.code)
        return
    async with session_scope(sessionmaker) as db:
        done = await finish(db, concept_id, result=out.result, usage=out.usage, style_id=out.style_id)
    if not done:
        _log.warning("design_director_finish_skipped", extra={"concept_id": concept_id})
