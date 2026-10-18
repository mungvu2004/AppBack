"""#35 nhận `body.axes` và `body.origin` (G4b-17): lưới trục và gốc toạ độ lưu được, N16/N15 trả lại."""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.spatial_read.tests._helpers import make_scene
from apps.api.spatial_write.tests._route_helpers import layer_path, put_layer


def _axis(level_id: str, source: str = "human", reviewed: bool = True) -> dict[str, Any]:
    """Một `AxisSchema` dạng dây: trục dọc `A` dài 10 m của tầng `level_id`."""
    return {
        "id": "A-TESTAXIS01",
        "levelId": level_id,
        "label": "A",
        "direction": "vertical",
        "line": {"start": {"x": 0, "y": 0}, "end": {"x": 0, "y": 10000}},
        "confidence": 1.0,
        "source": source,
        "reviewed": reviewed,
    }


async def test_put_axes_and_origin_read_back(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Ghi trục + gốc → N16 trả đúng; lượt chỉ đổi gốc giữ nguyên trục; N15 cũng có trục."""
    scene = await make_scene(db_session)
    project_id, level_id = scene.project.id, scene.floors[0].level_id
    payload = {"baseVersion": 0, "body": {"axes": [_axis(level_id)], "origin": {"x": 1200, "y": -300}}}

    first = await put_layer(api_client, project_id, level_id, scene.owner, payload)
    moved = await put_layer(
        api_client, project_id, level_id, scene.owner, {"baseVersion": 1, "body": {"origin": {"x": 5, "y": 6}}}
    )

    assert (first.status_code, moved.status_code, moved.json()["revision"]) == (200, 200, 2)
    read = (await api_client.get(layer_path(project_id, level_id), headers=headers_of(scene.owner))).json()
    assert read["axes"] == [_axis(level_id)]
    assert read["origin"] == {"x": 5, "y": 6}
    graph = await api_client.get(f"/api/projects/{project_id}/spatial", headers=headers_of(scene.owner))
    assert [axis["id"] for axis in graph.json()["graph"]["axes"]] == ["A-TESTAXIS01"]


async def test_put_same_axes_twice_is_noop(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Gửi lại đúng trục đang có (base mới) → 200 không tăng bản ghi (bước 10 so cả trục và gốc)."""
    scene = await make_scene(db_session)
    project_id, level_id = scene.project.id, scene.floors[0].level_id
    body = {"axes": [_axis(level_id)], "origin": {"x": 0, "y": 0}}
    await put_layer(api_client, project_id, level_id, scene.owner, {"baseVersion": 0, "body": body})

    again = await put_layer(api_client, project_id, level_id, scene.owner, {"baseVersion": 1, "body": body})

    assert (again.status_code, again.json()["revision"]) == (200, 1)


async def test_put_axes_rejects_bad_items(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """A5 → `REVIEW_BY_AI_FORBIDDEN`, tầng khác → `LAYER_LEVEL_MISMATCH`, gốc thập phân → `VALIDATION`."""
    scene = await make_scene(db_session)
    project_id, level_id = scene.project.id, scene.floors[0].level_id
    cases = [
        ({"axes": [_axis(level_id, source="ai", reviewed=True)]}, "REVIEW_BY_AI_FORBIDDEN", "body.axes.0.reviewed"),
        ({"axes": [_axis("L-OTHER00001")]}, "LAYER_LEVEL_MISMATCH", "body.axes.0.levelId"),
        ({"axes": [_axis(level_id), _axis(level_id)]}, "VALIDATION", "body.axes.1.id"),
    ]
    for body, code, field in cases:
        response = await put_layer(api_client, project_id, level_id, scene.owner, {"baseVersion": 0, "body": body})
        assert (response.status_code, response.json()["code"], response.json().get("field")) == (422, code, field)

    bad_origin = {"baseVersion": 0, "body": {"origin": {"x": 1.5, "y": 0}}}
    response = await put_layer(api_client, project_id, level_id, scene.owner, bad_origin)
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")
