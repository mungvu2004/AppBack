"""Tiện ích HTTP và dựng dữ liệu của test route #36, N17-N20 (không phải file test).

Ba nhóm lặp ở mọi file test route: đường và lượt gọi của năm `op`, dựng một dự án có tầng đã
`commit` (session của route và của test là hai kết nối khác nhau, nên chỉ dữ liệu đã `commit` mới
thấy), và làm hỏng một ảnh chụp bằng SQL. Dựng dự án dùng `make_scene` của B3-02, header dùng
`headers_of` của B2-01, ghi lớp dùng `write` của B3-03 — không có bản thứ hai ở đây.
"""

import logging
from dataclasses import dataclass
from typing import Any, Literal

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.spatial_read.tests._helpers import make_scene
from apps.api.spatial_write.tests._helpers import write
from apps.api.versions.snapshots import VersionRow, create_version
from packages.core.clock import Clock
from packages.db.models.auth import User
from packages.db.models.floors import FloorRow
from packages.domain.spatial import SpatialLayer

Corruption = Literal["purged", "schema", "alien_key"]

SNAPSHOT_LOGGER = "apps.api.versions.snapshots"
"""Logger ghi `snapshot_schema_mismatch` khi ảnh chụp lệch lược đồ hay hỏng."""


@dataclass(frozen=True)
class Stage:
    """Một dự án đã `commit`: người sở hữu, tầng đầu (và tầng thứ hai nếu có) — chỉ dữ liệu nguyên thuỷ."""

    owner: User
    project_id: str
    floor: FloorRow
    other_level_id: str | None

    @property
    def level_id(self) -> str:
        """`level_id` của tầng đầu — thứ FE gửi làm `floorId`."""
        return self.floor.level_id


async def make_stage(db: AsyncSession, *, members: list[User] | None = None, floors: int = 1) -> Stage:
    """Dự án + `floors` tầng + người sở hữu (và `members`), đã `commit`."""
    scene = await make_scene(db, floors=floors, members=members or [])
    other = scene.floors[1].level_id if floors > 1 else None
    return Stage(owner=scene.owner, project_id=scene.project.id, floor=scene.floors[0], other_level_id=other)


def versions_path(project_id: str, version_id: str | None = None, tail: str = "") -> str:
    """`/api/projects/{project_id}/versions[/{version_id}][/tail]`."""
    base = f"/api/projects/{project_id}/versions"
    return base if version_id is None else f"{base}/{version_id}{tail}"


async def call(client: httpx.AsyncClient, method: str, path: str, user: User, **kwargs: Any) -> httpx.Response:
    """Một request với người `user`; `kwargs` đi thẳng vào httpx (`params`, `json`, `headers` thêm)."""
    headers = {**headers_of(user), **kwargs.pop("headers", {})}
    return await client.request(method, path, headers=headers, **kwargs)


async def read_version(
    client: httpx.AsyncClient, stage: Stage, version_id: str, user: User | None = None
) -> httpx.Response:
    """#36."""
    return await call(client, "GET", versions_path(stage.project_id, version_id), user or stage.owner)


async def list_versions(
    client: httpx.AsyncClient, stage: Stage, *, user: User | None = None, floor_id: str | None = None, **params: Any
) -> httpx.Response:
    """N17; `floor_id` mặc định là tầng đầu, `floor_id=""` gửi rỗng, `params` thêm `cursor`/`limit`."""
    query = {"floorId": stage.level_id if floor_id is None else floor_id, **params}
    return await call(client, "GET", versions_path(stage.project_id), user or stage.owner, params=query)


async def read_snapshot(
    client: httpx.AsyncClient, stage: Stage, version_id: str, user: User | None = None, floor_id: str | None = None
) -> httpx.Response:
    """N18; `floor_id` mặc định là tầng đầu."""
    query = {"floorId": stage.level_id if floor_id is None else floor_id}
    return await call(
        client, "GET", versions_path(stage.project_id, version_id, "/snapshot"), user or stage.owner, params=query
    )


def restore_body(base: int, floor_id: str) -> dict[str, Any]:
    """Thân N19 `{baseVersion, body: {floorId}}`."""
    return {"baseVersion": base, "body": {"floorId": floor_id}}


async def restore(
    client: httpx.AsyncClient,
    stage: Stage,
    version_id: str,
    base: int,
    user: User | None = None,
    floor_id: str | None = None,
) -> httpx.Response:
    """N19; `floor_id` mặc định là tầng đầu."""
    payload = restore_body(base, stage.level_id if floor_id is None else floor_id)
    return await call(
        client, "POST", versions_path(stage.project_id, version_id, "/restore"), user or stage.owner, json=payload
    )


async def relabel(
    client: httpx.AsyncClient, stage: Stage, version_id: str, label: Any, user: User | None = None
) -> httpx.Response:
    """N20."""
    return await call(
        client,
        "PATCH",
        versions_path(stage.project_id, version_id, "/label"),
        user or stage.owner,
        json={"label": label},
    )


async def put_layer(
    db: AsyncSession, stage: Stage, clock: Clock, layer: SpatialLayer | None, *, base: int, **options: Any
) -> int:
    """Ghi một lớp bằng `write_layer` thật, `commit`, trả `revision` mới — dựng trạng thái trước lượt gọi."""
    result = await write(
        db, floor=stage.floor, actor=stage.owner, clock=clock, base_revision=base, layer=layer, **options
    )
    await db.commit()
    return result.revision


async def commit_snap(
    db: AsyncSession, stage: Stage, clock: Clock, *, actor: User | None = None, note: str | None = None
) -> VersionRow:
    """`create_version` thật cho tầng đầu rồi `commit`."""
    who = actor or stage.owner
    row = await create_version(
        db, floor_pk=stage.floor.pk, actor_id=who.id, actor_name=who.name, note=note, clock=clock
    )
    await db.commit()
    return row


async def corrupt_snapshot(db: AsyncSession, version_id: str, how: Corruption) -> None:
    """Làm hỏng ảnh chụp bằng SQL rồi `commit`: mất, `schemaVersion: 2`, hay khoá lạ trong `document`."""
    statements: dict[Corruption, str] = {
        "purged": "UPDATE versions SET snapshot = NULL WHERE id = :id",
        "schema": "UPDATE versions SET snapshot = jsonb_set(snapshot, '{schemaVersion}', '2') WHERE id = :id",
        "alien_key": "UPDATE versions SET snapshot = jsonb_set(snapshot, '{document,zzz}', '1') WHERE id = :id",
    }
    await db.execute(text(statements[how]), {"id": version_id})
    await db.commit()


def mismatch_logged(caplog: pytest.LogCaptureFixture) -> bool:
    """`snapshot_schema_mismatch` đã được ghi ở mức WARNING chưa (cần `caplog.set_level` trước lượt gọi)."""
    return any(r.msg == "snapshot_schema_mismatch" and r.levelno == logging.WARNING for r in caplog.records)
