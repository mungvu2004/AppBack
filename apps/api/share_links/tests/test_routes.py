"""Quyền máy chủ cho xuất mô hình và liên kết chia sẻ: từng vai, 404 trước 403, hết hạn, thu hồi."""

from datetime import timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.project_settings.tests.support import headers_of, seed_project
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock


async def _setup(db: AsyncSession):  # noqa: ANN202
    """Dự án có admin, engineer, viewer là thành viên + một admin ngoài dự án."""
    admin = await make_user(db, role="admin")
    engineer = await make_user(db, role="engineer")
    viewer = await make_user(db, role="viewer")
    outsider = await make_user(db, role="admin")
    project = await seed_project(db, owner=engineer, members=[admin, viewer])
    return project, admin, engineer, viewer, outsider


async def test_export_roles(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """admin/engineer 200, viewer 403, người ngoài (kể cả admin) 404."""
    project, admin, engineer, viewer, outsider = await _setup(db_session)
    path = f"/api/projects/{project.id}/exports"
    for user in (admin, engineer):
        response = await api_client.post(path, headers=headers_of(user), json={})
        assert response.status_code == 200, response.text
        assert "floorRevisions" in response.json()
    assert (await api_client.post(path, headers=headers_of(viewer), json={})).status_code == 403
    response = await api_client.post(path, headers=headers_of(outsider), json={})
    assert response.status_code == 404
    assert response.json()["resource"] == "project"
    assert (await api_client.post(path, json={})).status_code == 401


async def test_share_links_roles_and_lifecycle(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tạo/liệt kê/thu hồi theo vai; tuyến công khai mở được tới khi thu hồi."""
    project, admin, engineer, viewer, outsider = await _setup(db_session)
    path = f"/api/projects/{project.id}/share-links"
    assert (await api_client.post(path, headers=headers_of(viewer), json={})).status_code == 403
    assert (await api_client.get(path, headers=headers_of(viewer))).status_code == 403
    assert (await api_client.post(path, headers=headers_of(outsider), json={})).status_code == 404

    created = await api_client.post(path, headers=headers_of(engineer), json={"permission": "view", "label": "khách"})
    assert created.status_code == 201, created.text
    link = created.json()
    assert link["status"] == "active"
    assert link["passwordProtected"] is False
    token = link["url"].rsplit("/", 1)[1]
    assert len(token) >= 40

    listed = await api_client.get(path, headers=headers_of(admin))
    assert [item["id"] for item in listed.json()] == [link["id"]]

    opened = await api_client.get(f"/api/share/{token}")
    assert opened.status_code == 200, opened.text
    assert opened.json()["link"]["id"] == link["id"]

    item = f"{path}/{link['id']}"
    assert (await api_client.delete(item, headers=headers_of(viewer))).status_code == 403
    assert (await api_client.delete(item, headers=headers_of(outsider))).status_code == 404
    assert (await api_client.delete(f"{path}/shl_nope", headers=headers_of(admin))).status_code == 404
    revoked = await api_client.delete(item, headers=headers_of(admin))
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert (await api_client.get(f"/api/share/{token}")).status_code == 404


async def test_share_link_expired_and_unknown_token(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Hết hạn → `expired` trong danh sách và 404 ở tuyến công khai; token bịa → 404."""
    project, _, engineer, _, _ = await _setup(db_session)
    path = f"/api/projects/{project.id}/share-links"
    expires = (fake_clock.now() + timedelta(hours=1)).isoformat()
    created = await api_client.post(path, headers=headers_of(engineer), json={"expiresAt": expires})
    assert created.status_code == 201, created.text
    token = created.json()["url"].rsplit("/", 1)[1]
    assert (await api_client.get(f"/api/share/{token}")).status_code == 200
    fake_clock.advance(timedelta(hours=2))
    assert (await api_client.get(f"/api/share/{token}")).status_code == 404
    assert (await api_client.get(path, headers=headers_of(engineer))).json()[0]["status"] == "expired"
    assert (await api_client.get("/api/share/not-a-real-token")).status_code == 404
