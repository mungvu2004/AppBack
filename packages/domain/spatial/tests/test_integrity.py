"""Toàn vẹn lớp một tầng: mỗi luật và mức một ca, thứ tự ổn định, thứ tự cao độ tầng."""

from collections.abc import Iterator

import pytest

from packages.domain.spatial import (
    IntegrityIssue,
    Point,
    SpatialLayer,
    check_integrity,
    check_level_order,
    has_critical,
    sample_building,
    sample_layer,
)

LAYER = sample_layer(0)
WALL, OTHER_WALL = LAYER.walls[0], LAYER.walls[1]
OPENING = LAYER.openings[0]
ROOM, ITEM = LAYER.rooms[0], LAYER.furniture[0]
EMPTY = SpatialLayer(walls=(), openings=(), rooms=(), furniture=())


issue = IntegrityIssue


def layer(**lists: object) -> SpatialLayer:
    """Lớp chỉ chứa các danh sách truyền vào (không kiểm lại mô hình: dữ liệu hợp lệ nhưng lệch nhau)."""
    return EMPTY.model_copy(update=lists)


@pytest.mark.parametrize("index", range(4))
def test_sample_layers_are_clean(index: int) -> None:
    """Bốn lớp của mẫu A14 không có lỗi, kể cả khi truyền đúng `level_id`."""
    sample = sample_layer(index)
    assert check_integrity(sample) == []
    assert check_integrity(sample, level_id=sample.walls[0].level_id) == []


def test_empty_layer_is_clean() -> None:
    """Lớp rỗng không có lỗi, kể cả khi truyền `level_id`."""
    assert check_integrity(EMPTY, level_id="L-LEVEL000000") == []


def test_orphan_opening_is_critical() -> None:
    """Ô mở trỏ về tường không có → critical, `ref_id` là tường bị trỏ."""
    assert check_integrity(layer(openings=(OPENING,))) == [
        issue("missingReference", "critical", OPENING.id, OPENING.wall_id)
    ]


def test_wall_listing_unknown_opening_is_critical() -> None:
    """Tường liệt kê ô mở không có → critical."""
    assert check_integrity(layer(walls=(WALL,))) == [issue("missingReference", "critical", WALL.id, OPENING.id)]


def test_wall_not_listing_its_opening_is_a_warning() -> None:
    """Ô mở trỏ về tường mà tường không liệt kê nó → warning gắn vào tường."""
    bare = WALL.model_copy(update={"opening_ids": ()})
    assert check_integrity(layer(walls=(bare,), openings=(OPENING,))) == [
        issue("missingReference", "warning", WALL.id, OPENING.id)
    ]


def test_unknown_room_of_furniture_is_a_warning() -> None:
    """`roomId` lạ → warning; không có `roomId` thì không lỗi."""
    assert check_integrity(layer(furniture=(ITEM,))) == [issue("missingReference", "warning", ITEM.id, ROOM.id)]
    assert check_integrity(layer(furniture=(ITEM.model_copy(update={"room_id": None}),))) == []


def test_unknown_wall_of_room_is_a_warning() -> None:
    """`wallIds` lạ → warning."""
    assert check_integrity(layer(rooms=(ROOM,))) == [issue("missingReference", "warning", ROOM.id, WALL.id)]


def test_duplicate_wall_id_is_reported_once() -> None:
    """Cùng id ba lần trên hai danh sách tường → một lỗi critical (W4 theo loại nên tường không trùng phòng)."""
    twin = OTHER_WALL.model_copy(update={"id": WALL.id})
    issues = check_integrity(LAYER.model_copy(update={"walls": (*LAYER.walls, twin, twin)}))
    assert [found for found in issues if found.rule == "duplicateId"] == [issue("duplicateId", "critical", WALL.id)]


def test_foreign_level_is_critical() -> None:
    """Khác `levelId` của thực thể đầu tiên → critical, `ref_id` là tầng lạ."""
    stray = ROOM.model_copy(update={"level_id": "L-LEVEL000001"})
    tampered = LAYER.model_copy(update={"rooms": (*LAYER.rooms[1:], stray)})
    assert check_integrity(tampered) == [issue("levelMembership", "critical", ROOM.id, "L-LEVEL000001")]


def test_explicit_level_id_wins_over_the_first_entity() -> None:
    """Truyền `level_id` thì mọi thực thể khác tầng đó đều lỗi, kể cả thực thể đầu tiên."""
    issues = check_integrity(layer(walls=(WALL,), openings=(OPENING,)), level_id="L-LEVEL000002")
    assert issues == [issue("levelMembership", "critical", WALL.id, WALL.level_id)]


def test_repeated_first_point_is_a_warning() -> None:
    """Điểm đầu lặp ở cuối đường bao → warning."""
    closed = ROOM.model_copy(update={"outline": (*ROOM.outline, ROOM.outline[0])})
    tampered = LAYER.model_copy(update={"rooms": (closed, *LAYER.rooms[1:])})
    assert check_integrity(tampered) == [issue("roomOutline", "warning", ROOM.id)]


def test_rules_come_in_fixed_order_and_are_stable() -> None:
    """Nhóm theo luật (trùng → tham chiếu → tầng → đường bao); gọi lại cho y hệt."""
    closed = ROOM.model_copy(update={"outline": (*ROOM.outline, Point(x=0, y=0))})
    stray = ITEM.model_copy(update={"level_id": "L-LEVEL000003", "room_id": "R-GHOST0000000"})
    broken = layer(walls=(WALL, WALL), openings=(OPENING,), rooms=(closed,), furniture=(stray,))
    assert check_integrity(broken) == [
        issue("duplicateId", "critical", WALL.id),
        issue("missingReference", "warning", ITEM.id, "R-GHOST0000000"),
        issue("levelMembership", "critical", ITEM.id, "L-LEVEL000003"),
        issue("roomOutline", "warning", ROOM.id),
    ]
    assert check_integrity(broken) == check_integrity(broken)


def test_references_follow_list_order() -> None:
    """Trong một luật: tường → ô mở → phòng → đồ đạc."""
    gone_opening, gone_wall, gone_room = "D-GONE00000000", "W-GONE00000000", "R-GONE00000000"
    broken = layer(
        walls=(WALL.model_copy(update={"opening_ids": (OPENING.id, gone_opening)}),),
        openings=(OPENING.model_copy(update={"wall_id": gone_wall}),),
        rooms=(ROOM.model_copy(update={"wall_ids": (gone_wall,)}),),
        furniture=(ITEM.model_copy(update={"room_id": gone_room}),),
    )
    assert check_integrity(broken) == [
        issue("missingReference", "critical", WALL.id, gone_opening),
        issue("missingReference", "critical", OPENING.id, gone_wall),
        issue("missingReference", "warning", ROOM.id, gone_wall),
        issue("missingReference", "warning", ITEM.id, gone_room),
    ]


class ScanCounter(tuple[str, ...]):
    """`openingIds` đếm số lượt bị quét (lặp hay `in`), để chốt độ phức tạp mà không đo giờ (TEST-02)."""

    scans = 0

    def __iter__(self) -> Iterator[str]:
        """Một lượt lặp là một lượt quét."""
        self.scans += 1
        return super().__iter__()

    def __contains__(self, item: object) -> bool:
        """`in` trên tuple là một lượt quét tuyến tính."""
        self.scans += 1
        return super().__contains__(item)


def test_hosted_openings_do_not_rescan_the_wall_list() -> None:
    """Mỗi tường quét `openingIds` số lượt cố định, không theo số ô mở trỏ về nó (R-25, review B3-01 #1).

    Quét lại cho mỗi ô mở là O(N x M) trên thân #35 do client gửi: 41,8 s CPU với 7,8 MiB.
    """
    listed = ScanCounter(f"D-LIST{index:08d}" for index in range(50))
    hosted = tuple(OPENING.model_copy(update={"id": f"D-HOST{index:08d}"}) for index in range(200))
    issues = check_integrity(layer(walls=(WALL.model_copy(update={"opening_ids": listed}),), openings=hosted))
    assert [found.severity for found in issues] == ["critical"] * 50 + ["warning"] * 200
    assert listed.scans <= 2


def test_twin_walls_check_hosted_openings_once() -> None:
    """Ba tường trùng id, hai ô mở trỏ về id đó: hai cảnh báo, không phải 3 x 2 (review B3-01 lượt 2, N1).

    Xét lại cho mỗi bản trùng là W x N lỗi trên thân #35 do client gửi: 3,16 MiB cạn 4 GiB.
    """
    bare = WALL.model_copy(update={"opening_ids": ()})
    twin = OPENING.model_copy(update={"id": "D-HOST00000000"})
    assert check_integrity(layer(walls=(bare, bare, bare), openings=(OPENING, twin))) == [
        issue("duplicateId", "critical", WALL.id),
        issue("missingReference", "warning", WALL.id, OPENING.id),
        issue("missingReference", "warning", WALL.id, twin.id),
    ]


def test_has_critical() -> None:
    """Chỉ `critical` chặn; cảnh báo không."""
    assert has_critical([issue("roomOutline", "warning", ROOM.id), issue("duplicateId", "critical", WALL.id)])
    assert not has_critical([issue("roomOutline", "warning", ROOM.id)])
    assert not has_critical([])


def test_level_order() -> None:
    """Sắp theo `order` (không theo thứ tự danh sách), cao độ phải tăng ngặt; bằng nhau cũng là lỗi."""
    levels = sample_building().levels
    assert check_level_order(levels) == []
    assert check_level_order(tuple(reversed(levels))) == []
    flat = levels[2].model_copy(update={"elevation_mm": levels[1].elevation_mm})
    sunk = levels[3].model_copy(update={"elevation_mm": 0})
    assert check_level_order((levels[0], levels[1], flat, sunk)) == [
        issue("levelElevationOrder", "warning", flat.id, levels[1].id),
        issue("levelElevationOrder", "warning", sunk.id, flat.id),
    ]
    assert check_level_order([]) == []
