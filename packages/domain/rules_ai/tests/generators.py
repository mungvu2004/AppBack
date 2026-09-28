"""Bộ sinh lớp ngẫu nhiên có hạt giống cho test: `current` (người/AI, duyệt/chưa) và `ai` (đầu ra pipeline).

Cả hai lớp dựng từ **cùng một mặt bằng gốc** (lưới phòng 4 x 4 m, gốc có thể âm) với nhiễu ±0/30/60 mm,
nên phòng, tường, đồ đạc của hai bên thật sự chạm nhau ở biên dung sai. Id đúng W4 theo loại; `current`
không có mục `ai` + `reviewed` (A5), không lỗi critical, không tham chiếu treo. Hạt giống chia hết cho
4 (25 %, ≥ 20 % yêu cầu) cho `ai` dùng lại id cùng loại của `current`.
"""

import random
from dataclasses import dataclass
from typing import Any, Final

from packages.domain.rules_ai.tests.builders import (
    box_room,
    furniture,
    layer,
    opening,
    wall,
    with_openings,
)
from packages.domain.spatial import Furniture, Opening, Room, SpatialLayer, Wall

CELL_MM: Final = 4000
_JITTERS: Final = (0, 30, 60)
_GAPS: Final = (0, 40, 60, 200, 300, 301, 400)
_FURNITURE_KINDS: Final = ("sanitaryFixture", "kitchenCabinet", "table", "bed", "chair")
_AI_ID_BASE: Final = 500_000


@dataclass(frozen=True, slots=True)
class Pair:
    """Cặp đầu vào một hạt giống: lớp hiện có, kết quả pipeline, và có dùng chung id không."""

    seed: int
    current: SpatialLayer
    ai: SpatialLayer
    shared_ids: bool


def shares_ids(seed: int) -> bool:
    """Hạt giống dùng chung id giữa `current` và `ai`: 1 trong 4."""
    return seed % 4 == 0


def _flags(rng: random.Random, *, is_current: bool) -> dict[str, Any]:
    """Cờ duyệt: `ai` luôn AI chưa duyệt; `current` trộn người/AI, duyệt/chưa nhưng không bao giờ AI + duyệt."""
    confidence = round(rng.uniform(0.2, 0.95), 2)
    if not is_current:
        return {"source": "ai", "reviewed": False, "confidence": confidence}
    source = rng.choice(("ai", "ai", "human"))
    reviewed = source == "human" and rng.random() < 0.6
    return {"source": source, "reviewed": reviewed, "confidence": confidence}


class _Plan:
    """Dựng một lớp từ mặt bằng gốc; `slot` đánh số ổn định để hai lớp chia sẻ id khi cần."""

    def __init__(self, rng: random.Random, plan: list[tuple[int, int]], *, is_current: bool, id_base: int) -> None:
        """`plan` là ô lưới (cột, hàng) có phòng, đã cộng gốc; `id_base` cộng vào số thứ tự id."""
        self.rng, self.plan, self.is_current, self.id_base = rng, plan, is_current, id_base
        self.walls: list[Wall] = []
        self.openings: list[Opening] = []
        self.rooms: list[Room] = []
        self.furniture: list[Furniture] = []

    def _jitter(self) -> int:
        """Nhiễu ngẫu nhiên một toạ độ."""
        j = self.rng.choice(_JITTERS)
        return self.rng.randint(-j, j)

    def build(self, origin: tuple[int, int]) -> SpatialLayer:
        """Dựng phòng, bốn tường mỗi phòng, ô mở, đồ đạc; mọi tham chiếu đều hợp lệ."""
        for slot, (col, row) in enumerate(self.plan):
            x0, y0 = origin[0] + col * CELL_MM, origin[1] + row * CELL_MM
            self._room(slot, (x0, y0), (x0 + CELL_MM, y0 + CELL_MM))
        return layer(
            walls=with_openings(tuple(self.walls), tuple(self.openings)),
            openings=tuple(self.openings),
            rooms=tuple(self.rooms),
            furniture_items=tuple(self.furniture),
        )

    def _room(self, slot: int, low: tuple[int, int], high: tuple[int, int]) -> None:
        """Một phòng + bốn tường + đồ đạc; số id = `id_base + slot * 10 + chỉ số`."""
        base = self.id_base + slot * 10
        corners = [(low[0], low[1]), (high[0], low[1]), (high[0], high[1]), (low[0], high[1])]
        wall_ids = []
        for side in range(4):
            start, end = corners[side], corners[(side + 1) % 4]
            number = base + side
            item = wall(
                number,
                (start[0] + self._jitter(), start[1] + self._jitter()),
                (end[0] + self._jitter(), end[1] + self._jitter()),
                kind=self.rng.choice(("partition", "envelope", "loadBearing")),
                thickness=self.rng.choice((100, 200, 220)),
                **_flags(self.rng, is_current=self.is_current),
            )
            self.walls.append(item)
            wall_ids.append(item.id)
            if self.rng.random() < 0.5:
                self.openings.append(
                    opening(
                        number,
                        number,
                        kind=self.rng.choice(("window", "window", "door")),
                        **_flags(self.rng, is_current=self.is_current),
                    )
                )
        self.rooms.append(
            box_room(
                base,
                (low[0] + self._jitter(), low[1] + self._jitter()),
                (high[0] + self._jitter(), high[1] + self._jitter()),
                wall_ids=tuple(wall_ids),
                **_flags(self.rng, is_current=self.is_current),
            )
        )
        self._furniture(base, low, high)

    def _furniture(self, base: int, low: tuple[int, int], high: tuple[int, int]) -> None:
        """Một đồ áp tường tây với khe ngẫu nhiên và hai đồ tuỳ ý; `roomId` trỏ phòng vừa dựng hoặc vắng."""
        room_id = self.rooms[-1].id
        gap = self.rng.choice(_GAPS)
        middle = (low[1] + high[1]) // 2
        self.furniture.append(
            furniture(
                base,
                (low[0] + 50 + gap + 300, middle),
                kind=self.rng.choice(_FURNITURE_KINDS[:2]),
                room_id=room_id,
                **_flags(self.rng, is_current=self.is_current),
            )
        )
        for extra in range(1, self.rng.randint(1, 3)):
            centre = (self.rng.randint(low[0], high[0]), self.rng.randint(low[1], high[1]))
            self.furniture.append(
                furniture(
                    base + extra,
                    centre,
                    kind=self.rng.choice(_FURNITURE_KINDS),
                    size=self.rng.choice((400, 600, 800)),
                    room_id=self.rng.choice((room_id, None)),
                    **_flags(self.rng, is_current=self.is_current),
                )
            )


def random_pair(seed: int) -> Pair:
    """Cặp `(current, ai)` xác định theo `seed` (`random.Random(seed)`, BE-00 §9)."""
    rng = random.Random(seed)  # noqa: S311 — bộ sinh thử tất định theo hạt giống (BE-00 §9)
    origin = (rng.randrange(-6000, 6001, 10), rng.randrange(-6000, 6001, 10))
    cells = [(col, row) for col in range(3) for row in range(2)]
    plan_current = [cell for cell in cells if rng.random() < 0.8] or cells[:1]
    plan_ai = [cell for cell in plan_current if rng.random() < 0.85] + [c for c in cells if rng.random() < 0.15]
    shared = shares_ids(seed)
    current = _Plan(rng, plan_current, is_current=True, id_base=1000).build(origin)
    ai = _Plan(rng, plan_ai or cells[:1], is_current=False, id_base=1000 if shared else _AI_ID_BASE).build(origin)
    return Pair(seed, current, ai, shared)
