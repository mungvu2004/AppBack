"""Toàn vẹn lớp không gian một tầng: gương `src/domain/spatial/integrity.ts` (chỉ đọc, không sửa dữ liệu).

Luật chạy theo thứ tự cố định; trong một luật, theo thứ tự `walls → openings →
rooms → furniture` rồi thứ tự trong danh sách, nên hai lần gọi cho cùng kết quả.
Không có câu chữ: `rule` + `severity` + id là đủ cho máy (B3-03 đổi sang
`LAYER_INTEGRITY_BROKEN`). Tường dài 0 và phòng dưới ba điểm đã bị mô hình chặn,
nên không có luật riêng như FE.
"""

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from packages.domain.spatial.model import Furniture, Level, Room, SpatialLayer, Wall

IntegrityRule = Literal["duplicateId", "missingReference", "levelMembership", "roomOutline", "levelElevationOrder"]
IntegritySeverity = Literal["critical", "warning"]


@dataclass(frozen=True, slots=True)
class IntegrityIssue:
    """Một lỗi: thực thể mang lỗi (`entity_id`) và id nó trỏ tới hay so với (`ref_id`), nếu có."""

    rule: IntegrityRule
    severity: IntegritySeverity
    entity_id: str
    ref_id: str | None = None


def _duplicate_ids(layer: SpatialLayer) -> list[IntegrityIssue]:
    """Id xuất hiện hơn một lần trên cả bốn danh sách; mỗi id báo một lần, theo lần gặp đầu."""
    counts = Counter(entity.id for entity in layer.entities())
    return [IntegrityIssue("duplicateId", "critical", entity_id) for entity_id, n in counts.items() if n > 1]


def _missing_references(layer: SpatialLayer) -> list[IntegrityIssue]:
    """Tham chiếu trỏ vào hư không; mức theo `integrity.ts:85-229`, `ref_id` là id bị trỏ."""
    wall_ids = {wall.id for wall in layer.walls}
    opening_ids = {opening.id for opening in layer.openings}
    room_ids = {room.id for room in layer.rooms}
    hosted: dict[str, list[str]] = {}
    for opening in layer.openings:
        hosted.setdefault(opening.wall_id, []).append(opening.id)

    issues: list[IntegrityIssue] = []
    for wall in layer.walls:
        issues += [_missing(wall.id, ref, "critical") for ref in wall.opening_ids if ref not in opening_ids]
        # Ô mở trỏ về tường mà tường không liệt kê: vẽ được, chỉ lệch chỉ mục. Tra bằng `set`:
        # quét `tuple` cho mỗi ô mở là O(N x M) trên thân #35 do client gửi (R-25). `pop`: chỉ tường
        # đầu tiên mang id xét các ô mở của id đó; bản trùng (đã `duplicateId`) mà xét lại là W x N lỗi.
        listed = set(wall.opening_ids)
        issues += [_missing(wall.id, ref, "warning") for ref in hosted.pop(wall.id, ()) if ref not in listed]
    issues += [_missing(o.id, o.wall_id, "critical") for o in layer.openings if o.wall_id not in wall_ids]
    for room in layer.rooms:
        issues += [_missing(room.id, ref, "warning") for ref in room.wall_ids if ref not in wall_ids]
    issues += [
        _missing(item.id, item.room_id, "warning")
        for item in layer.furniture
        if item.room_id is not None and item.room_id not in room_ids
    ]
    return issues


def _missing(entity_id: str, ref_id: str, severity: IntegritySeverity) -> IntegrityIssue:
    """Dựng một lỗi `missingReference`."""
    return IntegrityIssue("missingReference", severity, entity_id, ref_id)


def _level_membership(layer: SpatialLayer, level_id: str | None) -> list[IntegrityIssue]:
    """Tường, phòng, đồ đạc phải cùng một tầng: `level_id` khi truyền, không thì tầng của thực thể đầu tiên."""
    members: tuple[Wall | Room | Furniture, ...] = (*layer.walls, *layer.rooms, *layer.furniture)
    if not members:
        return []
    expected = members[0].level_id if level_id is None else level_id
    return [
        IntegrityIssue("levelMembership", "critical", entity.id, entity.level_id)
        for entity in members
        if entity.level_id != expected
    ]


def _room_outlines(layer: SpatialLayer) -> list[IntegrityIssue]:
    """Đường bao lặp điểm đầu ở cuối (quy ước là không lặp): cảnh báo."""
    closed = [room for room in layer.rooms if room.outline[0] == room.outline[-1]]
    return [IntegrityIssue("roomOutline", "warning", room.id) for room in closed]


def check_integrity(layer: SpatialLayer, *, level_id: str | None = None) -> list[IntegrityIssue]:
    """Chạy bốn luật của một lớp và trả mọi lỗi, nhóm theo luật; lớp rỗng lỗi là danh sách rỗng."""
    return [
        *_duplicate_ids(layer),
        *_missing_references(layer),
        *_level_membership(layer, level_id),
        *_room_outlines(layer),
    ]


def check_level_order(levels: Sequence[Level]) -> list[IntegrityIssue]:
    """Sắp theo `order` (ổn định), `elevationMm` phải tăng ngặt; `ref_id` là tầng ngay dưới."""
    ordered = sorted(levels, key=lambda level: level.order)
    return [
        IntegrityIssue("levelElevationOrder", "warning", upper.id, lower.id)
        for lower, upper in pairwise(ordered)
        if upper.elevation_mm <= lower.elevation_mm
    ]


def has_critical(issues: Iterable[IntegrityIssue]) -> bool:
    """Có lỗi chặn ghi hay không; cảnh báo thì không chặn."""
    return any(issue.severity == "critical" for issue in issues)
