"""PERF-03 P27: `ETag` yếu + 304 cho N15/N16 (`cached_json`), thân không đổi so với trước."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.spatial_read.http_cache import CACHE_CONTROL, etag_matches
from apps.api.spatial_read.tests._helpers import make_scene
from apps.api.spatial_read.tests._read_helpers import graph_path, layer_path
from packages.testing.factories.spatial import make_floor_document, sample_floor_layer
from packages.testing.fixtures.clock import FakeClock


def test_matches__weak_comparison_lists_and_star() -> None:
    """So sánh yếu: bỏ `W/`, nhận danh sách cách dấu phẩy và `*`; rỗng hay khác → không khớp."""
    etag = 'W/"abc"'
    assert etag_matches('W/"abc"', etag)
    assert etag_matches('"abc"', etag)
    assert etag_matches('W/"zzz", W/"abc"', etag)
    assert etag_matches("*", etag)
    assert not etag_matches(None, etag)
    assert not etag_matches("", etag)
    assert not etag_matches('W/"abcd"', etag)


async def test_layer_etag__304_when_matching_200_otherwise(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """N16: lượt đầu 200 + `ETag`; gửi lại đúng tag → 304 không thân; tag khác → 200 cùng thân."""
    scene = await make_scene(db_session, floors=1)
    floor = scene.floors[0]
    await make_floor_document(
        db_session,
        floor_pk=floor.pk,
        layer=sample_floor_layer(0, level_id=floor.level_id),
        revision=2,
        clock=fake_clock,
    )
    await db_session.commit()
    path = layer_path(scene.project.id, floor.level_id)
    headers = headers_of(scene.owner)

    first = await api_client.get(path, headers=headers)
    assert first.status_code == 200
    assert first.headers["content-type"] == "application/json"
    assert first.headers["cache-control"] == CACHE_CONTROL
    etag = first.headers["etag"]
    assert etag.startswith('W/"')
    assert first.json()["revision"] == 2

    cached = await api_client.get(path, headers={**headers, "If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.content == b""
    assert cached.headers["etag"] == etag

    other = await api_client.get(path, headers={**headers, "If-None-Match": 'W/"stale"'})
    assert other.status_code == 200
    assert other.content == first.content


async def test_graph_etag__changes_with_revision(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """N15: tag cũ không còn khớp khi tài liệu tầng có `revision` mới → 200 với thân mới."""
    scene = await make_scene(db_session, floors=1)
    floor = scene.floors[0]
    headers = headers_of(scene.owner)
    path = graph_path(scene.project.id)

    empty = await api_client.get(path, headers=headers)
    assert empty.status_code == 200
    old_tag = empty.headers["etag"]
    assert (await api_client.get(path, headers={**headers, "If-None-Match": old_tag})).status_code == 304

    await make_floor_document(
        db_session,
        floor_pk=floor.pk,
        layer=sample_floor_layer(0, level_id=floor.level_id),
        revision=5,
        clock=fake_clock,
    )
    await db_session.commit()
    fresh = await api_client.get(path, headers={**headers, "If-None-Match": old_tag})
    assert fresh.status_code == 200
    assert fresh.headers["etag"] != old_tag
    assert fresh.json()["floorRevisions"] == [{"floorId": floor.level_id, "revision": 5}]
