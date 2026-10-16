"""#35 — duyệt QC qua ghi lớp đòi `qc.approve` ở máy chủ (NFR-02), không chỉ `layer.edit`.

"Duyệt" là lượt ghi làm một thực thể hay kích thước **mới** mang `reviewed=True` (chưa duyệt →
duyệt, hay thêm hẳn một mục đã duyệt). Ma trận thật cho `qc.approve` và `layer.edit` cùng giá trị
ở mọi vai, nên các ca "thiếu `qc.approve`" chạy dưới fixture `engineer_without_qc_approve`.
"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.spatial_read.documents import load_document
from apps.api.spatial_read.tests._helpers import Scene, make_scene
from apps.api.spatial_write.tests._helpers import make_dimension, make_wall, review, simple_layer
from apps.api.spatial_write.tests._route_helpers import make_furniture, put_layer, wire, write_body
from packages.db.models.auth import User
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.permissions import assert_forbidden


async def _unreviewed_floor(client: httpx.AsyncClient, scene: Scene) -> None:
    """Người sở hữu ghi `revision 1`: một tường AI chưa duyệt."""
    level_id = scene.floors[0].level_id
    first = await put_layer(
        client, scene.project.id, level_id, scene.owner, write_body(0, layer=simple_layer(level_id))
    )
    assert first.status_code == 200, first.text


async def _approve(client: httpx.AsyncClient, scene: Scene, user: User) -> httpx.Response:
    """`user` duyệt tường của `revision 1` (người sửa đổi nguồn sang `human`, `reviewed=True`)."""
    level_id = scene.floors[0].level_id
    approved = simple_layer(level_id, walls=(make_wall(level_id, source="human", reviewed=True),))
    return await put_layer(client, scene.project.id, level_id, user, write_body(1, layer=approved))


@pytest.mark.parametrize(
    ("role", "member", "status"),
    [("viewer", True, 403), ("engineer", True, 200), ("admin", True, 200), ("admin", False, 404)],
)
async def test_spatial_write_layer__qc_approve_by_role(
    api_client: httpx.AsyncClient, db_session: AsyncSession, role: str, member: bool, status: int
) -> None:
    """Duyệt QC theo ma trận: viewer 403, engineer/admin thành viên 200, người ngoài 404 `project` (K08)."""
    user = await make_user(db_session, role=role)
    scene = await make_scene(db_session, members=[user] if member else [])
    await _unreviewed_floor(api_client, scene)

    response = await _approve(api_client, scene, user)

    assert response.status_code == status, response.text
    if status == 403:
        assert_forbidden(response)
    elif status == 404:
        assert response.json()["resource"] == "project"
    else:
        assert response.json()["layer"]["walls"][0]["reviewed"] is True


@pytest.mark.usefixtures("engineer_without_qc_approve")
async def test_spatial_write_layer__approve_without_qc_approve(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Có `layer.edit`, thiếu `qc.approve` → 403; tài liệu vẫn ở `revision 1`, tường chưa duyệt."""
    scene = await make_scene(db_session)
    await _unreviewed_floor(api_client, scene)

    response = await _approve(api_client, scene, scene.owner)

    assert_forbidden(response)
    await db_session.commit()
    document = await load_document(db_session, scene.floors[0].pk)
    assert document is not None
    assert (document.revision, document.layer.walls[0].reviewed) == (1, False)


@pytest.mark.usefixtures("engineer_without_qc_approve")
async def test_spatial_write_layer__new_reviewed_entity_without_qc_approve(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Thêm hẳn một tường đã duyệt cũng là duyệt → 403 khi thiếu `qc.approve`."""
    scene = await make_scene(db_session)
    level_id = scene.floors[0].level_id
    layer = simple_layer(level_id, walls=(make_wall(level_id, source="human", reviewed=True),))

    response = await put_layer(api_client, scene.project.id, level_id, scene.owner, write_body(0, layer=layer))

    assert_forbidden(response)


@pytest.mark.usefixtures("engineer_without_qc_approve")
async def test_spatial_write_layer__dimension_approve_without_qc_approve(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Kích thước mới mang `reviewed=True` (BUG-577) → 403 khi thiếu `qc.approve`."""
    scene = await make_scene(db_session)
    level_id = scene.floors[0].level_id
    dimension = {**wire(make_dimension(level_id)), **review(source="human", reviewed=True)}
    payload = {"baseVersion": 0, "body": {"dimensions": [dimension]}}

    response = await put_layer(api_client, scene.project.id, level_id, scene.owner, payload)

    assert_forbidden(response)


@pytest.mark.usefixtures("engineer_without_qc_approve")
async def test_spatial_write_layer__edit_keeps_approval_without_qc_approve(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Admin đã duyệt tường; engineer thiếu `qc.approve` vẫn sửa phần khác (giữ nguyên dấu duyệt) → 200."""
    admin = await make_user(db_session, role="admin")
    scene = await make_scene(db_session, members=[admin])
    level_id = scene.floors[0].level_id
    await _unreviewed_floor(api_client, scene)
    assert (await _approve(api_client, scene, admin)).status_code == 200
    reviewed_wall = make_wall(level_id, source="human", reviewed=True)
    edited = simple_layer(level_id, walls=(reviewed_wall,), furniture=(make_furniture(level_id),))

    response = await put_layer(api_client, scene.project.id, level_id, scene.owner, write_body(2, layer=edited))

    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 3


@pytest.mark.usefixtures("engineer_without_qc_approve")
async def test_spatial_write_layer__unapprove_without_qc_approve(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Bỏ duyệt không cấp dấu duyệt nào → engineer thiếu `qc.approve` vẫn được, 200 và tường chưa duyệt."""
    admin = await make_user(db_session, role="admin")
    scene = await make_scene(db_session, members=[admin])
    level_id = scene.floors[0].level_id
    await _unreviewed_floor(api_client, scene)
    assert (await _approve(api_client, scene, admin)).status_code == 200
    unapproved = simple_layer(level_id, walls=(make_wall(level_id, source="human", reviewed=False),))

    response = await put_layer(api_client, scene.project.id, level_id, scene.owner, write_body(2, layer=unapproved))

    assert response.status_code == 200, response.text
    assert response.json()["layer"]["walls"][0]["reviewed"] is False
