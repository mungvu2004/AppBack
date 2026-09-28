"""Nền dựng dùng chung cho mọi test của `apps.api.versions` (B3-04: việc D, R).

Bốn thứ lặp lại ở gần như mọi file: một tầng đã có tài liệu (tuỳ chọn tỉ lệ) và người ghi có
tên, một lượt đổi tài liệu **thật** qua `write_layer`, đặt trần lưu giữ ảnh chụp, và đọc lại
bảng `versions` bằng session khác (test đồng thời chỉ tin những gì đã `commit`).

Dựng dự án + tầng và session thứ hai dùng `make_scene`, `other_session`, `race` của
`apps/api/spatial_read/tests/_helpers.py`; đổi tài liệu dùng `write` của
`apps/api/spatial_write/tests/_helpers.py` — không có bản thứ hai ở đây.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.spatial_read.documents import load_document
from apps.api.spatial_read.tests._helpers import Scene, make_scene
from apps.api.spatial_write.tests._helpers import make_wall, simple_layer, write
from apps.api.versions import snapshots
from apps.api.versions.snapshots import VersionRow, VersionsSettings, create_version, reset_versions_settings_cache
from packages.core.clock import Clock
from packages.db.models.auth import User
from packages.db.models.floors import FloorRow
from packages.db.models.versions import VersionRecord
from packages.testing.factories.spatial import make_floor_document

PIPELINE_ACTOR: Final = "system:pipeline"
"""`creator_id` của bản do pipeline AI sinh (B5-06b)."""


@dataclass(frozen=True)
class VersionScene:
    """Một tầng đã `commit` cùng người ghi có tên; `floor` là tầng duy nhất của `scene`."""

    scene: Scene
    floor: FloorRow
    actor: User


def keep_snapshots(monkeypatch: pytest.MonkeyPatch, n: int) -> None:
    """Đặt `VERSIONS_KEEP_SNAPSHOTS = n` cho đúng một test và để cache cấu hình sạch sau đó.

    `setenv` + reset cache như mọi cấu hình lười của repo, rồi thay `get_versions_settings` bằng
    một bản **không cache**: `monkeypatch` khôi phục hàm gốc khi test xong, nên không cache nào
    mang trần `n` sang test sau.
    """
    monkeypatch.setenv("VERSIONS_KEEP_SNAPSHOTS", str(n))
    reset_versions_settings_cache()
    monkeypatch.setattr(snapshots, "get_versions_settings", VersionsSettings)


async def make_version_scene(
    db: AsyncSession,
    clock: Clock,
    *,
    document: bool = True,
    scale: Decimal | None = None,
    name: str = "Nguyễn Văn An",
) -> VersionScene:
    """Dự án + một tầng (đã `commit`); `document=False` để tầng chưa có dòng `floor_documents`.

    `scale` khác `None` ghi tỉ lệ nguồn `human` (CHECK `scale_source_matches_scale`). Lớp ban đầu
    là một tường AI dài 1000 mm — đủ để một lượt `bump` sau đó thật sự đổi tài liệu.
    """
    scene = await make_scene(db)
    floor = scene.floors[0]
    scene.owner.name = name
    if document:
        await make_floor_document(
            db,
            floor_pk=floor.pk,
            layer=simple_layer(floor.level_id),
            scale=scale,
            scale_source="none" if scale is None else "human",
            clock=clock,
        )
    await db.commit()
    return VersionScene(scene=scene, floor=floor, actor=scene.owner)


async def bump(db: AsyncSession, vs: VersionScene, clock: Clock, *, length: int) -> int:
    """Đổi tài liệu bằng `write_layer` thật (tường dài `length` mm); trả `revision` mới, chưa `commit`."""
    document = await load_document(db, vs.floor.pk)
    assert document is not None
    layer = simple_layer(vs.floor.level_id, walls=[make_wall(vs.floor.level_id, length=length)])
    result = await write(db, floor=vs.floor, actor=vs.actor, clock=clock, base_revision=document.revision, layer=layer)
    assert result.applied
    return result.revision


async def snap(db: AsyncSession, vs: VersionScene, clock: Clock, *, note: str | None = None) -> VersionRow:
    """`create_version` cho người ghi của cảnh; chưa `commit`."""
    return await create_version(
        db, floor_pk=vs.floor.pk, actor_id=vs.actor.id, actor_name=vs.actor.name, note=note, clock=clock
    )


async def versions_of(sessionmaker: async_sessionmaker[AsyncSession], floor_pk: int) -> list[VersionRecord]:
    """Mọi dòng `versions` của tầng theo `sequence` tăng dần, đọc bằng session **mới** (chỉ thấy phần đã commit)."""
    async with sessionmaker() as session:
        stmt = select(VersionRecord).where(VersionRecord.floor_pk == floor_pk).order_by(VersionRecord.sequence)
        return list((await session.execute(stmt)).scalars().all())
