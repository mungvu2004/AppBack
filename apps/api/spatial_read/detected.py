"""Hai route đọc phần ML đã dò của lượt mới nhất (QT-SCALE-API, D1 giai-phap-phan4).

`dimension-strings`: chữ kích thước toàn số trong `dimensionReading/text.json` để màn tỉ lệ
gợi ý chuỗi đo. `detected-geometry`: điểm bắt, bề dày tường, cửa, phòng lớn nhất và hộp bao
ngoài theo **px của trang** `pages/0-<id>.png` — để FE đặt tỉ lệ bằng một cú bấm.

Chỉ đọc: chưa có lượt `completed`, artifact vắng hay hỏng → danh sách rỗng chứ không lỗi; đây là
gợi ý, không phải dữ liệu bắt buộc. Không trả `span_px` (hợp đồng lô 2).
"""

import math
import re
import statistics
from collections.abc import Sequence
from typing import Final, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.wire import KeepNull, WireModel
from packages.db.models.drawings import DrawingRow, PipelineRunRow
from packages.domain.spatial import SpatialLayer
from packages.ml_contracts.artifacts import (
    ARTIFACT_JSON_MAX_BYTES,
    STEP_ARTIFACTS,
    BoxPx,
    DetectionPx,
    TextPx,
    WallPx,
    objects_from_json,
    text_from_json,
    walls_from_json,
)
from packages.ml_contracts.families import ModelFamily
from packages.storage import keys
from packages.storage.port import ObjectStorage, read_all_capped

DIMENSION_MIN_MM: Final = 300
DIMENSION_MAX_MM: Final = 30_000
SNAP_MERGE_PX: Final = 3.0
"""Hai điểm bắt cách nhau dưới ngần này px gộp làm một (nét vẽ dày vài px)."""
DOOR_LABELS: Final = frozenset({"door", "double_door"})
_DIGITS: Final = re.compile(r"[0-9]+")


class BoxPxOut(WireModel):
    """Hộp thẳng trục trên trang, px."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float


class DimensionStringOut(WireModel):
    """Một chuỗi kích thước toàn số đọc được."""

    id: str
    text: str
    value_mm: int
    box: BoxPxOut
    confidence: float
    orientation: Literal["horizontal", "vertical"]


class DimensionStringsOut(WireModel):
    """`GET …/dimension-strings`; chưa có lượt → `runId`/`pagePx` `null`, `items` rỗng."""

    run_id: KeepNull[str | None]
    page_px: KeepNull[tuple[int, int] | None]
    items: tuple[DimensionStringOut, ...]


class ThicknessPxOut(WireModel):
    """Bề dày tường theo px: trung vị và phân vị 90."""

    median: float
    p90: float


class SnapPointOut(WireModel):
    """Điểm bắt: đầu tường hay giao điểm hai tường."""

    x: float
    y: float
    kind: Literal["wallEnd", "junction"]


class DoorOut(WireModel):
    """Cửa dò được (`door`/`double_door`); `widthPx` là cạnh dài của hộp."""

    id: str
    box: BoxPxOut
    width_px: float
    confidence: float


class LargestRoomOut(WireModel):
    """Phòng lớn nhất của lớp đã lưu, hộp đổi mm → px bằng tỉ lệ tầng."""

    room_id: str
    box_px: BoxPxOut
    label: str


class DetectedGeometryOut(WireModel):
    """`GET …/detected-geometry`; chưa có lượt hay artifact → danh sách rỗng, hộp/bề dày `null`."""

    page_px: KeepNull[tuple[int, int] | None]
    wall_thickness_px: KeepNull[ThicknessPxOut | None]
    snap_points: tuple[SnapPointOut, ...]
    doors: tuple[DoorOut, ...]
    largest_room: KeepNull[LargestRoomOut | None]
    outer_box_px: KeepNull[BoxPxOut | None]


def _box(box: BoxPx) -> BoxPxOut:
    return BoxPxOut(x_min=box.x_min, y_min=box.y_min, x_max=box.x_max, y_max=box.y_max)


def dimension_items(texts: Sequence[TextPx]) -> tuple[DimensionStringOut, ...]:
    """Chữ toàn số (bỏ `.`, `,`, khoảng trắng) trong [300, 30 000] mm; `id` theo vị trí trong `text.json`."""
    out: list[DimensionStringOut] = []
    for index, item in enumerate(texts):
        digits = re.sub(r"[.,\s]", "", item.text)
        if not _DIGITS.fullmatch(digits):
            continue
        value = int(digits)
        if not DIMENSION_MIN_MM <= value <= DIMENSION_MAX_MM:
            continue
        wide = item.box.x_max - item.box.x_min >= item.box.y_max - item.box.y_min
        out.append(
            DimensionStringOut(
                id=f"dim-{index}",
                text=item.text,
                value_mm=value,
                box=_box(item.box),
                confidence=item.confidence,
                orientation="horizontal" if wide else "vertical",
            )
        )
    return tuple(out)


def _intersection(a: WallPx, b: WallPx) -> tuple[float, float] | None:
    """Giao điểm hai đoạn (kể cả chữ T: đầu đoạn này nằm trên đoạn kia); song song → `None`."""
    ax, ay, bx, by = a.start.x, a.start.y, a.end.x, a.end.y
    cx, cy, dx, dy = b.start.x, b.start.y, b.end.x, b.end.y
    rx, ry, sx, sy = bx - ax, by - ay, dx - cx, dy - cy
    denom = rx * sy - ry * sx
    if abs(denom) < 1e-9:
        return None
    t = ((cx - ax) * sy - (cy - ay) * sx) / denom
    u = ((cx - ax) * ry - (cy - ay) * rx) / denom
    # Dung sai theo px chứ không theo tham số: đoạn dài 1000 px thì 1e-3 đã là 1 px.
    tol_t = SNAP_MERGE_PX / max(math.hypot(rx, ry), 1e-9)
    tol_u = SNAP_MERGE_PX / max(math.hypot(sx, sy), 1e-9)
    if -tol_t <= t <= 1 + tol_t and -tol_u <= u <= 1 + tol_u:
        return ax + t * rx, ay + t * ry
    return None


def snap_points(walls: Sequence[WallPx]) -> tuple[SnapPointOut, ...]:
    """Hai đầu mỗi đoạn + giao điểm từng cặp, gộp điểm cách < 3 px (giao điểm thắng đầu tường).

    Điểm gộp giữ toạ độ của điểm đầu tiên trong cụm, nên kết quả không đổi giữa hai lượt đọc.
    """
    # ponytail: O(n²) cả giao cặp lẫn gộp điểm — vài trăm đoạn mỗi trang; lưới băm nếu lên hàng nghìn.
    raw: list[tuple[float, float, Literal["wallEnd", "junction"]]] = []
    for wall in walls:
        raw.append((wall.start.x, wall.start.y, "wallEnd"))
        raw.append((wall.end.x, wall.end.y, "wallEnd"))
    for i, first in enumerate(walls):
        for second in walls[i + 1 :]:
            hit = _intersection(first, second)
            if hit is not None:
                raw.append((hit[0], hit[1], "junction"))
    merged: list[list[float | str]] = []
    for x, y, kind in raw:
        for point in merged:
            if math.hypot(x - float(point[0]), y - float(point[1])) < SNAP_MERGE_PX:
                if kind == "junction":
                    point[2] = "junction"
                break
        else:
            merged.append([x, y, kind])
    return tuple(
        SnapPointOut(x=round(float(x), 1), y=round(float(y), 1), kind="junction" if kind == "junction" else "wallEnd")
        for x, y, kind in merged
    )


def thickness(walls: Sequence[WallPx]) -> ThicknessPxOut | None:
    """Trung vị và p90 (hạng gần nhất) của `thickness_px`; không có tường → `None`."""
    if not walls:
        return None
    values = sorted(wall.thickness_px for wall in walls)
    p90 = values[math.ceil(0.9 * len(values)) - 1]
    return ThicknessPxOut(median=round(statistics.median(values), 1), p90=round(p90, 1))


def outer_box(walls: Sequence[WallPx]) -> BoxPxOut | None:
    """Hộp bao mọi đầu đoạn tường; không có tường → `None`."""
    if not walls:
        return None
    xs = [x for wall in walls for x in (wall.start.x, wall.end.x)]
    ys = [y for wall in walls for y in (wall.start.y, wall.end.y)]
    return BoxPxOut(x_min=min(xs), y_min=min(ys), x_max=max(xs), y_max=max(ys))


def doors(detections: Sequence[DetectionPx]) -> tuple[DoorOut, ...]:
    """Ô mở nhãn `door`/`double_door`; `id` theo vị trí trong `objects.json`."""
    return tuple(
        DoorOut(
            id=f"door-{index}",
            box=_box(item.box),
            width_px=round(max(item.box.x_max - item.box.x_min, item.box.y_max - item.box.y_min), 1),
            confidence=item.confidence,
        )
        for index, item in enumerate(detections)
        if item.label in DOOR_LABELS
    )


def largest_room(layer: SpatialLayer, mm_per_px: float | None) -> LargestRoomOut | None:
    """Phòng diện tích lớn nhất, hộp viền mm ÷ tỉ lệ; chưa có phòng hay tỉ lệ → `None`.

    Không trừ `origin` của tài liệu: lớp do pipeline dựng có gốc ở góc trang (px · tỉ lệ).
    """
    if not layer.rooms or not mm_per_px:
        return None
    room = max(layer.rooms, key=lambda candidate: candidate.area_m2)
    xs = [point.x / mm_per_px for point in room.outline]
    ys = [point.y / mm_per_px for point in room.outline]
    box = BoxPxOut(x_min=round(min(xs), 1), y_min=round(min(ys), 1), x_max=round(max(xs), 1), y_max=round(max(ys), 1))
    return LargestRoomOut(room_id=room.id, box_px=box, label=room.name)


class _MissingError(Exception):
    """Artifact vắng hay quá trần — với route gợi ý, cả hai nghĩa là "không có gì để gợi ý"."""


async def latest_run(db: AsyncSession, floor_pk: int) -> tuple[str, str] | None:
    """(`run_id`, `upload_id`) của lượt `completed` mới nhất chưa bị thay — cùng luật `latest_run_facts`."""
    stmt = (
        select(PipelineRunRow.id, PipelineRunRow.upload_id)
        .where(
            PipelineRunRow.floor_pk == floor_pk,
            PipelineRunRow.status == "completed",
            PipelineRunRow.superseded_by.is_(None),
        )
        .order_by(PipelineRunRow.created_at.desc(), PipelineRunRow.id.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).one_or_none()
    return None if row is None else (row[0], row[1])


async def page_px(db: AsyncSession, floor_pk: int) -> tuple[int, int] | None:
    """Cỡ trang bản vẽ hiện hành của tầng; chưa có bản vẽ → `None`."""
    stmt = select(DrawingRow.width_px, DrawingRow.height_px).where(DrawingRow.floor_pk == floor_pk)
    row = (await db.execute(stmt)).one_or_none()
    return None if row is None else (row[0], row[1])


async def read_artifact(
    storage: ObjectStorage, *, project_id: str, floor_id: str, run: tuple[str, str], step: ModelFamily
) -> bytes | None:
    """Bytes của artifact JSON đầu tiên của `step` trong lượt; vắng hay quá trần → `None`."""
    run_id, upload_id = run
    key = keys.run_artifact(project_id, floor_id, upload_id, run_id, step, STEP_ARTIFACTS[step][0])
    try:
        return await read_all_capped(
            storage, key, max_bytes=ARTIFACT_JSON_MAX_BYTES, too_large=_MissingError, on_missing=_MissingError
        )
    except _MissingError:
        return None


def parse_texts(data: bytes | None) -> tuple[TextPx, ...]:
    """`text.json` → mục; vắng hay sai hợp đồng → rỗng (gợi ý, không làm hỏng màn)."""
    if data is None:
        return ()
    try:
        return text_from_json(data).items
    except ValueError:
        return ()


def parse_walls(data: bytes | None) -> tuple[WallPx, ...]:
    """`walls.json` → đoạn; vắng hay hỏng → rỗng."""
    if data is None:
        return ()
    try:
        return walls_from_json(data).walls
    except ValueError:
        return ()


def parse_detections(data: bytes | None) -> tuple[DetectionPx, ...]:
    """`objects.json` → phát hiện; vắng hay hỏng → rỗng."""
    if data is None:
        return ()
    try:
        return objects_from_json(data).detections
    except ValueError:
        return ()
