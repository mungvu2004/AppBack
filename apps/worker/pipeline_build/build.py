"""Lắp ráp lớp không gian từ ba artifact ML (B5-05 [6] bước 1, 2, 7, 8) và khuôn `layer.json`.

Bước 3-6 nằm ở `geometry.py`, `rooms.py`; module này chỉ lọc đầu vào không tin được, chốt tỉ lệ,
dựng `Dimension`, chạy luật hậu xử lý và đóng gói `BuiltLayer`. Hàm thuần, không I/O, không sửa
đối số: mọi lỗi hợp đồng là `ValueError` để task đổi thành `PIPELINE_BUILD_INVALID`.
"""

import json
import logging
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final, Literal, Self

import numpy as np
import shapely
from shapely import STRtree

from apps.worker.pipeline_build.constants import DROPPED_KEYS
from apps.worker.pipeline_build.geometry import Scaling, WallSet, build_walls
from apps.worker.pipeline_build.ids import new_spatial_id
from apps.worker.pipeline_build.rooms import build_furniture, build_rooms
from packages.core.clock import Clock
from packages.core.pipeline import PipelineCode
from packages.domain.rules_ai import apply_post_rules
from packages.domain.scale import (
    RescaleError,
    ScaleSample,
    classify_scale_range,
    infer_scale,
    rescale_dimensions,
    rescale_unreviewed,
)
from packages.domain.spatial import (
    Dimension,
    Segment,
    SpatialLayer,
    Wall,
    check_integrity,
    has_critical,
    js_round,
)
from packages.ml_contracts.artifacts import (
    MAX_DETECTIONS,
    MAX_TEXTS,
    MAX_WALLS,
    DetectionPx,
    ObjectsResult,
    TextPx,
    TextResult,
    WallPx,
    WallsResult,
)
from packages.vision.dimensions import pair_dimension_lines, wall_spans

_log = logging.getLogger(__name__)

SCHEMA_VERSION: Final = 1
"""`layer.json` v1 (B5-05 [2]); số khác là file của bản khác, không đoán mà đọc."""

_QUANTUM: Final = Decimal("0.000001")
_SAMPLE_ID: Final = re.compile(r"^t(\d+)-w(\d+)-s(\d+|all)$")
"""Id mẫu thật của B5-04 (`pairing.py`): `sall` cho cả tường (prompt ghi `all`)."""

_DIMENSION_TOLERANCE: Final = 0.02
_BUILD_SCALE_TARGET_MM: Final = 150.0
"""Bề dày vách mong muốn khi phải tự chọn tỉ lệ dựng (B5-05 [6] bước 2)."""

_BUILD_SCALE_MIN: Final = 1.0
_BUILD_SCALE_MAX: Final = 200.0
_ROOT_KEYS: Final = frozenset({"schemaVersion", "layer", "dimensions", "scaleMmPerPx", "scaleSource", "dropped"})
_SCALE_SOURCES: Final = frozenset({"pipeline", "project_default"})
"""Hai giá trị `scaleSource` đã khai; B5-06b đọc `layer.json` qua `from_json` nên phải chặn ở đây."""


@dataclass(frozen=True, slots=True)
class BuiltLayer:
    """Kết quả một lượt dựng: lớp, kích thước, tỉ lệ đã chốt và bộ đếm mục bị bỏ.

    `dropped` luôn đủ 12 khoá `DROPPED_KEYS` nên bảng theo dõi của B5-06c không phải đoán khoá
    vắng. `to_json` cho byte tất định (cùng đầu vào → cùng file), `from_json` là nghịch đảo đúng.
    """

    layer: SpatialLayer
    dimensions: tuple[Dimension, ...]
    scale_mm_per_px: Decimal
    scale_source: Literal["pipeline", "project_default"]
    dropped: Mapping[str, int]

    def to_json(self) -> bytes:
        """`layer.json` UTF-8 gọn, khoá theo thứ tự cố định; `scaleMmPerPx` là chuỗi Decimal."""
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "layer": self.layer.model_dump(mode="json", by_alias=True, exclude_none=True),
            "dimensions": [item.model_dump(mode="json", by_alias=True, exclude_none=True) for item in self.dimensions],
            "scaleMmPerPx": str(self.scale_mm_per_px),
            "scaleSource": self.scale_source,
            "dropped": {key: self.dropped[key] for key in DROPPED_KEYS},
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()

    @classmethod
    def from_json(cls, data: bytes) -> Self:
        """Đọc `layer.json`; JSON hỏng, `schemaVersion` khác 1, khoá lạ hay thiếu → `ValueError`."""
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError("layer.json không phải JSON hợp lệ") from exc
        if not isinstance(payload, dict) or set(payload) != _ROOT_KEYS:
            raise ValueError("layer.json sai bộ khoá gốc")
        if payload["schemaVersion"] != SCHEMA_VERSION:
            raise ValueError(f"layer.json schemaVersion lạ: {payload['schemaVersion']!r}")
        dropped = payload["dropped"]
        if not isinstance(dropped, dict) or set(dropped) != set(DROPPED_KEYS):
            raise ValueError("layer.json sai bộ khoá dropped")
        if payload["scaleSource"] not in _SCALE_SOURCES:
            raise ValueError(f"layer.json scaleSource lạ: {payload['scaleSource']!r}")
        return cls(
            layer=SpatialLayer.model_validate(payload["layer"]),
            dimensions=tuple(Dimension.model_validate(item) for item in payload["dimensions"]),
            scale_mm_per_px=Decimal(payload["scaleMmPerPx"]),
            scale_source=payload["scaleSource"],
            dropped={key: int(dropped[key]) for key in DROPPED_KEYS},
        )


def _checked(raw: np.ndarray, what: str) -> None:
    """Mảng `[toạ độ…, confidence]`: NaN, vô cực hay `confidence` ngoài `[0, 1]` → `ValueError`.

    Đối số có thể dựng bằng `model_construct` nên không tin ràng buộc của B5-01 (bước 1).
    """
    if raw.size == 0:
        return
    if not bool(np.isfinite(raw).all()):
        raise ValueError(f"{what} chứa NaN hay vô cực")
    confidence = raw[:, -1]
    if not bool(((confidence >= 0.0) & (confidence <= 1.0)).all()):
        raise ValueError(f"{what} có confidence ngoài [0, 1]")


def _inside(coords: np.ndarray, width_px: int, height_px: int) -> np.ndarray:
    """Mặt nạ mục nằm trong `[-1, w+1] x [-1, h+1]`; cột chẵn là x, cột lẻ là y."""
    if coords.size == 0:
        return np.ones(len(coords), dtype=bool)
    xs, ys = coords[:, 0::2], coords[:, 1::2]
    return (
        (xs >= -1.0).all(axis=1)
        & (xs <= width_px + 1.0).all(axis=1)
        & (ys >= -1.0).all(axis=1)
        & (ys <= height_px + 1.0).all(axis=1)
    )


def _kept[T](items: Sequence[T], raw: np.ndarray, size: tuple[int, int], dropped: Counter[str]) -> tuple[T, ...]:
    """Mục còn lại sau bước 1; mục ra ngoài ảnh bị bỏ và đếm `outOfImage`."""
    mask = _inside(raw[:, :-1], *size)
    dropped["outOfImage"] += int(len(items) - mask.sum())
    return tuple(item for item, keep in zip(items, mask, strict=True) if keep)


def _filtered_walls(walls: Sequence[WallPx], size: tuple[int, int], dropped: Counter[str]) -> tuple[WallPx, ...]:
    """Tường hợp lệ và nằm trong ảnh; kiểm bằng numpy để chịu được trần 20.000 tường."""
    if len(walls) > MAX_WALLS:
        raise ValueError(f"{len(walls)} tường, trần {MAX_WALLS}")
    raw = np.array(
        [(w.start.x, w.start.y, w.end.x, w.end.y, w.thickness_px, w.confidence) for w in walls],
        dtype=float,
    ).reshape(len(walls), 6)
    _checked(raw, "walls")
    if raw.size and not bool((raw[:, 4] > 0.0).all()):
        raise ValueError("walls có thickness_px không dương")
    if raw.size and bool((raw[:, :2] == raw[:, 2:4]).all(axis=1).any()):
        raise ValueError("walls có tường hai đầu trùng nhau")
    return _kept(walls, np.delete(raw, 4, axis=1), size, dropped)


def _filtered_boxes[T: DetectionPx | TextPx](
    items: Sequence[T], limit: int, size: tuple[int, int], dropped: Counter[str], what: str
) -> tuple[T, ...]:
    """Hộp phát hiện hay chữ đã lọc như `_filtered_walls`: cùng luật vì cùng `BoxPx`."""
    if len(items) > limit:
        raise ValueError(f"{len(items)} {what}, trần {limit}")
    raw = np.array(
        [(i.box.x_min, i.box.y_min, i.box.x_max, i.box.y_max, i.confidence) for i in items],
        dtype=float,
    ).reshape(len(items), 5)
    _checked(raw, what)
    return _kept(items, raw, size, dropped)


def _resolved_scale(
    walls: Sequence[WallPx],
    texts: Sequence[TextPx],
    fallback_mm_per_px: Decimal,
    dropped: Counter[str],
) -> tuple[Decimal, Literal["pipeline", "project_default"], tuple[ScaleSample, ...], tuple[str, ...]]:
    """Bước 2: tỉ lệ dây `s`, nguồn, mẫu và id mẫu bị loại; ngoài khoảng → `scaleOutOfRange`.

    Không có tỉ lệ suy được, ngoài khoảng, hay `s` về 0 sau quantize → `fallback_mm_per_px`
    và log `SCALE_UNRESOLVED` (K19: không bao giờ đoán một tỉ lệ khác).
    """
    samples = pair_dimension_lines(texts, walls)
    result = infer_scale(samples)
    if result.mm_per_px is not None:
        if classify_scale_range(result.mm_per_px) == "inRange":
            value = Decimal(repr(result.mm_per_px)).quantize(_QUANTUM)
            if value != 0:
                return value, "pipeline", samples, result.rejected_ids
        else:
            dropped["scaleOutOfRange"] += 1
    _log.info(
        "pipeline_build_dropped",
        extra={"code": PipelineCode.SCALE_UNRESOLVED.value, "reason": result.reason},
    )
    return fallback_mm_per_px, "project_default", samples, result.rejected_ids


def _build_scale(walls: Sequence[WallPx], final: float) -> float:
    """`s_dựng` khi `project_default`: bề dày trung vị về 150 mm, kẹp `[1, 200]` (bước 2)."""
    if not walls:
        return final
    median = float(np.median(np.array([wall.thickness_px for wall in walls], dtype=float)))
    return min(max(_BUILD_SCALE_TARGET_MM / median, _BUILD_SCALE_MIN), _BUILD_SCALE_MAX)


def _ratio(sample: ScaleSample) -> float:
    """Tỉ lệ mm/px mà một mẫu ngụ ý."""
    return sample.real_length_mm / sample.pixel_length


def _whole_line(wall_px: WallPx, scaling: Scaling) -> Segment | None:
    """Cả đường tim của tường gốc `j` (mẫu `sall`), mm.

    Không dùng `Wall.centreline` của tường đã giữ: tường gộp ở 3b dài hơn tường gốc mà
    `valueMm` đo trên tường gốc, nên `line` sẽ lệch xa hơn ngưỡng 2 % của bước 7 (F3).
    """
    start = scaling.point(wall_px.start.x, wall_px.start.y)
    end = scaling.point(wall_px.end.x, wall_px.end.y)
    return None if start == end else Segment(start=start, end=end)


def _span_line(wall_px: WallPx, spans: Sequence[float], tag: str, scaling: Scaling) -> Segment | None:
    """Nhịp `k` của tường gốc đổi sang mm; nhịp suy biến sau làm tròn → `None` (không dựng được).

    `spans` là tham số dọc tường tính bằng px (`pairing._merge_points`), nên điểm chia là
    `start + t · đơn vị hướng`.
    """
    index = int(tag)
    if index + 1 >= len(spans):
        return None
    dx, dy = wall_px.end.x - wall_px.start.x, wall_px.end.y - wall_px.start.y
    length = math.hypot(dx, dy)
    ends = [
        scaling.point(wall_px.start.x + dx * spans[k] / length, wall_px.start.y + dy * spans[k] / length)
        for k in (index, index + 1)
    ]
    return None if ends[0] == ends[1] else Segment(start=ends[0], end=ends[1])


def _best_sample(
    candidates: Sequence[tuple[ScaleSample, int, str]], scale: float
) -> tuple[ScaleSample, int, str] | None:
    """Mẫu có tỉ số gần `s` nhất trong ngưỡng 2 %; không mẫu nào đạt → `None`."""
    within = [item for item in candidates if abs(_ratio(item[0]) - scale) / scale <= _DIMENSION_TOLERANCE]
    return min(within, key=lambda item: abs(_ratio(item[0]) - scale)) if within else None


def _grouped_samples(
    samples: Sequence[ScaleSample], rejected: frozenset[str], kept: Mapping[int, int]
) -> dict[int, list[tuple[ScaleSample, int, str]]]:
    """Mẫu còn dùng được, gom theo chỉ số chữ; chữ có mẫu bị loại hết vẫn có khoá (để đếm)."""
    grouped: dict[int, list[tuple[ScaleSample, int, str]]] = {}
    for sample in samples:
        match = _SAMPLE_ID.match(sample.id)
        if match is None:
            continue
        text_index, wall_index = int(match.group(1)), int(match.group(2))
        grouped.setdefault(text_index, [])
        if sample.id not in rejected and wall_index in kept and sample.pixel_length > 0:
            grouped[text_index].append((sample, wall_index, match.group(3)))
    return grouped


def _dimension(
    sample: ScaleSample, line: Segment, wall: Wall, text: TextPx, *, level_id: str, clock: Clock
) -> Dimension:
    """Một chuỗi kích thước tuyến tính do AI dựng; tin cậy là min của chữ và tường (bước 7)."""
    return Dimension(
        id=new_spatial_id("dimension", clock),
        level_id=level_id,
        kind="linear",
        reference_ids=(wall.id,),
        line=line,
        value_mm=js_round(sample.real_length_mm),
        confidence=min(text.confidence, wall.confidence),
        source="ai",
        reviewed=False,
    )


@dataclass(slots=True)
class _SpanIndex:
    """Điểm chia nhịp của một tường, tính trên tập con láng giềng thay vì cả 20.000 tường.

    `wall_spans(walls)[j]` chỉ phụ thuộc tường cắt tim `j` hoặc có đầu mút cách tim `j` không quá
    `max(t_j, t_k) / 2` (`pairing._WallIndex.spans`), nên một tập con **chứa đủ** các tường đó cho
    đúng kết quả ấy; tường thừa trong tập con không sinh thêm điểm chia. Gọi `wall_spans` trên cả
    bảng là O(n²), còn bước 7 chỉ cần vài tường có mẫu được chọn.
    """

    walls: Sequence[WallPx]
    tree: STRtree
    lines: np.ndarray
    reach: float
    cache: dict[int, tuple[float, ...]]

    @classmethod
    def of(cls, walls: Sequence[WallPx]) -> "_SpanIndex":
        """Dựng `STRtree` của mọi tim tường một lần cho cả lượt dựng."""
        coords = [[[w.start.x, w.start.y], [w.end.x, w.end.y]] for w in walls]
        lines = np.asarray(shapely.linestrings(coords), dtype=object)
        thickest = max((w.thickness_px for w in walls), default=0.0)
        return cls(walls, STRtree(lines), lines, thickest / 2, {})

    def spans(self, j: int) -> tuple[float, ...]:
        """Điểm chia nhịp của tường `j`, bằng `wall_spans(walls)[j]`; nhớ lại giữa các chữ."""
        if j not in self.cache:
            distance = max(self.walls[j].thickness_px / 2, self.reach)
            near = {int(k) for k in self.tree.query(self.lines[j], predicate="dwithin", distance=distance)}
            order = sorted(near | {j})
            self.cache[j] = wall_spans([self.walls[k] for k in order])[order.index(j)]
        return self.cache[j]


def _build_dimensions(
    context: "_Attempt", wall_set: WallSet, *, scaling: Scaling, clock: Clock, dropped: Counter[str]
) -> tuple[Dimension, ...]:
    """Bước 7: tối đa một `Dimension` mỗi chữ; chữ có mẫu mà không dựng được → `dimensionUnpaired`."""
    grouped = _grouped_samples(context.samples, frozenset(context.rejected), wall_set.input_to_wall)
    if not grouped:
        return ()
    index = _SpanIndex.of(context.walls_px)
    built: list[Dimension] = []
    for text_index in sorted(grouped):
        chosen = _best_sample(grouped[text_index], scaling.final)
        if chosen is None:
            dropped["dimensionUnpaired"] += 1
            continue
        sample, wall_index, tag = chosen
        wall = wall_set.walls[wall_set.input_to_wall[wall_index]]
        wall_px = context.walls_px[wall_index]
        line = (
            _whole_line(wall_px, scaling)
            if tag == "all"
            else _span_line(wall_px, index.spans(wall_index), tag, scaling)
        )
        if line is None:
            dropped["dimensionUnpaired"] += 1
            continue
        text = context.texts[text_index]
        built.append(_dimension(sample, line, wall, text, level_id=context.level_id, clock=clock))
    return tuple(built)


@dataclass(frozen=True, slots=True)
class _Attempt:
    """Đầu vào đã lọc của bước 3-8, dùng lại y nguyên cho lượt dựng lại sau `RescaleError`."""

    walls_px: tuple[WallPx, ...]
    detections: tuple[DetectionPx, ...]
    texts: tuple[TextPx, ...]
    samples: tuple[ScaleSample, ...]
    rejected: tuple[str, ...]
    level_id: str
    source: str


def _assembled(
    context: _Attempt, *, scaling: Scaling, clock: Clock, dropped: Counter[str]
) -> tuple[SpatialLayer, WallSet]:
    """Bước 3-6: lớp thô trước khi qua luật hậu xử lý, kèm `WallSet` cho bước 7."""
    shared: dict[str, Any] = {
        "level_id": context.level_id,
        "scaling": scaling,
        "clock": clock,
        "dropped": dropped,
    }
    wall_set = build_walls(context.walls_px, context.detections, **shared)
    rooms = build_rooms(wall_set.walls, wall_set.bridges, context.texts, **shared)
    furniture = build_furniture(context.detections, rooms, **shared)
    layer = SpatialLayer(walls=wall_set.walls, openings=wall_set.openings, rooms=rooms, furniture=furniture)
    return layer, wall_set


def _attempt(
    context: _Attempt, *, scaling: Scaling, clock: Clock, dropped: Counter[str]
) -> tuple[SpatialLayer, tuple[Dimension, ...]]:
    """Bước 3-8 ở `scaling.build`, đúng thứ tự khối [6]: 3-6, rồi 7, rồi 8.

    Bước 7 chạy trước `apply_post_rules` nên `Dimension.confidence` là `min(chữ, tường)` của
    tường lúc bước 7, chưa bị luật 2 hạ xuống; lỗi toàn vẹn critical sau luật → `ValueError`.
    """
    layer, wall_set = _assembled(context, scaling=scaling, clock=clock, dropped=dropped)
    dimensions: tuple[Dimension, ...] = ()
    if context.source == "pipeline":
        dimensions = _build_dimensions(context, wall_set, scaling=scaling, clock=clock, dropped=dropped)
    layer = apply_post_rules(layer)
    if has_critical(check_integrity(layer, level_id=context.level_id)):
        raise ValueError("lớp dựng ra có lỗi toàn vẹn critical")
    return layer, dimensions


def build_layer(
    *,
    level_id: str,
    walls: WallsResult,
    objects: ObjectsResult,
    text: TextResult,
    width_px: int,
    height_px: int,
    fallback_mm_per_px: Decimal,
    clock: Clock,
) -> BuiltLayer:
    """Ba artifact ML (px) → lớp không gian (mm) theo B5-05 [6]; không sửa đối số, không I/O.

    Đầu vào sai hợp đồng B5-01 (vượt trần, NaN, `confidence` ngoài `[0, 1]`, ảnh < 1 px,
    `fallback_mm_per_px` ≤ 0) → `ValueError`; đầu ra AI xấu chỉ bị bỏ và đếm vào `dropped`.
    Dựng ở `s_dựng` rồi đổi về `s`; `RescaleError` → dựng lại thẳng ở `s`, không ném.
    """
    if width_px < 1 or height_px < 1:
        raise ValueError(f"ảnh {width_px}x{height_px} px không hợp lệ")
    if not fallback_mm_per_px.is_finite() or fallback_mm_per_px <= 0:
        raise ValueError(f"fallback_mm_per_px {fallback_mm_per_px} phải dương và hữu hạn")
    size = (width_px, height_px)
    base: Counter[str] = Counter()
    walls_px = _filtered_walls(walls.walls, size, base)
    detections = _filtered_boxes(objects.detections, MAX_DETECTIONS, size, base, "detections")
    texts = _filtered_boxes(text.items, MAX_TEXTS, size, base, "texts")
    scale, source, samples, rejected = _resolved_scale(walls_px, texts, fallback_mm_per_px, base)
    final = float(scale)
    build = final if source == "pipeline" else _build_scale(walls_px, final)
    context = _Attempt(walls_px, detections, texts, samples, rejected, level_id, source)
    dropped = base.copy()
    layer, dimensions = _attempt(context, scaling=Scaling(build, final), clock=clock, dropped=dropped)
    if build != final:
        try:
            layer = rescale_unreviewed(layer, build, final)
            dimensions = rescale_dimensions(dimensions, build, final)
        except RescaleError as exc:
            _log.warning("pipeline_build_rescale_fallback", extra={"entity_id": exc.entity_id})
            dropped = base.copy()
            layer, dimensions = _attempt(context, scaling=Scaling(final, final), clock=clock, dropped=dropped)
    return BuiltLayer(
        layer=layer,
        dimensions=dimensions,
        scale_mm_per_px=scale,
        scale_source=source,
        dropped={key: dropped[key] for key in DROPPED_KEYS},
    )
