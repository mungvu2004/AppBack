"""Fixture lượt nướng ánh sáng đang xếp hàng: dự án thật, dòng `lighting_bakes`, `input.glb` trong kho local (LB-01)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.messaging.payloads.lighting_bake import LIGHTING_BAKE_INPUT
from packages.storage.keys import lighting_bake_object
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.auth import make_user
from packages.testing.factories.lighting_bake import make_lighting_bake
from packages.testing.factories.projects import make_project

INPUT_GLB = b"glTF" + (2).to_bytes(4, "little") + (24).to_bytes(4, "little") + b"\x04\x00\x00\x00JSON{}  "
"""GLB v2 nhỏ nhất `sniff` nhận là `glb` — đủ cho bộ Blender giả, Blender thật không dùng nó."""


@dataclass(frozen=True, slots=True)
class QueuedBake:
    """Một lượt `queued` đã có `input.glb` trong kho."""

    project_id: str
    bake_id: str


QueueBake = Callable[..., Awaitable[QueuedBake]]


@pytest.fixture
def queue_bake(db_sessionmaker: async_sessionmaker[AsyncSession], local_storage: LocalDiskStorage) -> QueueBake:
    """Hàm dựng lượt `queued`; truyền `project_id` để thêm lượt vào dự án sẵn có."""

    async def factory(*, project_id: str | None = None, status: str = "queued") -> QueuedBake:
        """Dự án (mới nếu không truyền) + dòng `lighting_bakes` + `input.glb`."""
        async with db_sessionmaker() as db:
            if project_id is None:
                owner = await make_user(db)
                project = await make_project(db, owner=owner)
                await db.commit()
                project_id = project.id
            row = await make_lighting_bake(db, project_id=project_id, status=status)
        key = lighting_bake_object(project_id, row.id, LIGHTING_BAKE_INPUT)
        await local_storage.put(key, INPUT_GLB, content_type="model/gltf-binary", max_bytes=len(INPUT_GLB) + 1)
        return QueuedBake(project_id=project_id, bake_id=row.id)

    return factory
