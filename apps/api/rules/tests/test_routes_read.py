"""Test hợp đồng của N21 `rules_read_config` (B3-05 [8]): Đ — C01 C06 C08 C17, cộng lọc khoá cũ."""

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.rules.tests.support import (
    get_config,
    put_config,
    replace_body,
    seed_admin_project,
    seed_project,
)
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock

_SAVED = {"DOOR-WIDTH": {"enabled": False, "severity": "critical", "thresholds": {"door.minWidthMm": 700}}}


async def test_rules_read_config__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Hai mẫu golden: chưa lưu → `{revision: 0, overrides: {}}` (không tạo dòng); đã lưu → đúng giá trị đã ghi."""
    owner, project = await seed_admin_project(db_session)
    viewer = await make_user(db_session, role="viewer")
    shared = await seed_project(db_session, owner=owner, members=[viewer])

    empty = await get_config(api_client, shared.id, viewer)
    assert empty.status_code == 200
    assert empty.json() == {"revision": 0, "overrides": {}}
    count = (await db_session.execute(text("SELECT count(*) FROM rule_configs"))).scalar_one()
    assert count == 0

    assert (await put_config(api_client, project.id, owner, replace_body(0, _SAVED))).status_code == 200
    saved = await get_config(api_client, project.id, owner)
    assert saved.json() == {"revision": 1, "overrides": _SAVED}


async def test_rules_read_config__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không phải thành viên → 404 `resource:"project"`, không phải 403."""
    _, project = await seed_admin_project(db_session)
    outsider = await make_user(db_session, role="admin")
    response = await get_config(api_client, project.id, outsider)
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_rules_read_config__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm (người gọi vẫn là thành viên) → 404."""
    owner = await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=owner, deleted_at=fake_clock.now())
    assert (await get_config(api_client, project.id, owner)).status_code == 404


async def test_rules_read_config__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`RuleOverride` chỉ có `thresholds` → vắng `enabled`, `severity` (không `null`)."""
    owner, project = await seed_admin_project(db_session)
    payload = {"WALL-LENGTH": {"thresholds": {"wall.minLengthMm": 100}}}
    await put_config(api_client, project.id, owner, replace_body(0, payload))
    read = await get_config(api_client, project.id, owner)
    assert read.json()["overrides"] == payload


async def test_rules_read_config__stale_entries_filtered(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Dòng ghi bằng SQL có mã/khoá cũ: N21 chỉ trả phần còn trong danh mục; PUT lại đúng thứ đó → 200."""
    owner, project = await seed_admin_project(db_session)
    stored = (
        '{"OLD-RULE": {"enabled": false},'
        ' "WALL-THICKNESS": {"thresholds": {"wall.oldMm": 5}},'
        ' "DOOR-WIDTH": {"severity": "warning"}}'
    )
    await db_session.execute(
        text("INSERT INTO rule_configs (project_id, revision, overrides) VALUES (:p, 3, CAST(:o AS jsonb))"),
        {"p": project.id, "o": stored},
    )
    await db_session.commit()

    read = await get_config(api_client, project.id, owner)
    assert read.json() == {"revision": 3, "overrides": {"DOOR-WIDTH": {"severity": "warning"}}}
    again = await put_config(api_client, project.id, owner, replace_body(3, read.json()["overrides"]))
    assert again.status_code == 200
    assert again.json()["revision"] == 4
