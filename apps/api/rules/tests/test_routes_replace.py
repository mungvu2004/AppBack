"""Test hợp đồng của N22 `rules_replace_config` (B3-05 [6], [8]): GV — C01-C03 C06-C09 C09b C17 C18.

C14 (hai người song song) ở `test_concurrency.py`; các từ chối theo mã ở `test_rejections.py`.
"""

from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.rules.tests.support import (
    config_path,
    get_config,
    headers_of,
    put_config,
    replace_body,
    seed_admin_project,
    seed_project,
)
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.access import activity_rows, assert_one_activity
from packages.testing.fixtures.clock import FakeClock

_CONFIG: dict[str, Any] = {
    "WALL-THICKNESS": {"enabled": True, "thresholds": {"wall.minThicknessMm": 100}},
    "GENERAL": {"thresholds": {"general.jointToleranceMm": 0}},
}


async def _stored(db_sessionmaker: async_sessionmaker[AsyncSession], project_id: str) -> Any:
    """Đọc dòng `rule_configs` qua session mới (K22)."""
    async with db_sessionmaker() as session:
        return (
            await session.execute(
                text("SELECT revision, overrides, last_writer_id FROM rule_configs WHERE project_id = :p"),
                {"p": project_id},
            )
        ).one_or_none()


async def test_rules_replace_config__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Ghi đầu `baseVersion: 0` → `revision: 1`; bền qua session mới (K22); người ghi là `sub` (K05)."""
    owner, project = await seed_admin_project(db_session)
    first = await put_config(api_client, project.id, owner, replace_body(0, _CONFIG))
    assert first.status_code == 200
    assert first.json() == {"revision": 1, "overrides": _CONFIG}
    row = await _stored(db_sessionmaker, project.id)
    assert (row.revision, row.overrides, row.last_writer_id) == (1, _CONFIG, owner.id)

    second = await put_config(api_client, project.id, owner, replace_body(1, {}))
    assert second.json() == {"revision": 2, "overrides": {}}


async def test_rules_replace_config__C01_same_config_still_writes(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Gửi lại đúng cấu hình đang có với `baseVersion = revision` vẫn là một lần ghi (tăng `revision`)."""
    owner, project = await seed_admin_project(db_session)
    await put_config(api_client, project.id, owner, replace_body(0, _CONFIG))
    again = await put_config(api_client, project.id, owner, replace_body(1, _CONFIG))
    assert again.json()["revision"] == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"WALL-LENGTH": {"severity": "info"}},
        {"WALL-LENGTH": {"thresholds": {"wall.minLengthMm": "100"}}},
        {"WALL-LENGTH": {"thresholds": {"wall.minLengthMm": True}}},
        {"WALL-LENGTH": {"enabled": "true"}},
        {"WALL-LENGTH": {"enabled": 1}},
        {"WALL-LENGTH": {"enabled": None}},
        {"WALL-LENGTH": {}},
        {"WALL-LENGTH": {"thresholds": {}}},
        {"WALL-LENGTH": {"enabled": True, "thresholds": {"wall": 1}}},
        {"wall-length": {"enabled": True}},
    ],
)
async def test_rules_replace_config__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, overrides: dict[str, Any]
) -> None:
    """Sai kiểu/mẫu, override rỗng, `thresholds` rỗng, `null` → 422 `VALIDATION`."""
    owner, project = await seed_admin_project(db_session)
    response = await put_config(api_client, project.id, owner, replace_body(0, overrides))
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_rules_replace_config__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ trong `body` và trong `RuleOverride` → 422 (W1)."""
    owner, project = await seed_admin_project(db_session)
    in_body = {"baseVersion": 0, "body": {"overrides": {}, "extra": 1}}
    in_override = replace_body(0, {"WALL-LENGTH": {"enabled": True, "note": "x"}})
    for payload in (in_body, in_override):
        response = await put_config(api_client, project.id, owner, payload)
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION"


async def test_rules_replace_config__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Người ngoài dự án, kể cả admin hệ thống → 404, không ghi gì."""
    _, project = await seed_admin_project(db_session)
    outsider = await make_user(db_session, role="admin")
    response = await put_config(api_client, project.id, outsider, replace_body(0))
    assert response.status_code == 404
    assert response.json()["resource"] == "project"
    assert (await db_session.execute(text("SELECT count(*) FROM rule_configs"))).scalar_one() == 0


async def test_rules_replace_config__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`engineer` (vai mạnh nhất không có `ruleset.edit`) → 403 `FORBIDDEN`, không ghi gì; quyền kiểm trước 428."""
    owner = await make_user(db_session, role="admin")
    engineer = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, members=[engineer])
    response = await put_config(api_client, project.id, engineer, replace_body(0, _CONFIG))
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    missing = await api_client.put(
        config_path(project.id), json={"body": {"overrides": {}}}, headers=headers_of(engineer)
    )
    assert missing.status_code == 403
    assert (await get_config(api_client, project.id, owner)).json() == {"revision": 0, "overrides": {}}


async def test_rules_replace_config__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm → 404."""
    owner = await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=owner, deleted_at=fake_clock.now())
    assert (await put_config(api_client, project.id, owner, replace_body(0))).status_code == 404


async def test_rules_replace_config__C09(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Base cũ → 409 thân W20; `baseVersion = revision + 1` cũng 409 (không 422); thiếu `baseVersion` → 428."""
    owner, project = await seed_admin_project(db_session)
    await put_config(api_client, project.id, owner, replace_body(0, _CONFIG))
    await put_config(api_client, project.id, owner, replace_body(1, {}))

    for stale in (1, 0, 3):
        response = await put_config(api_client, project.id, owner, replace_body(stale, _CONFIG))
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "VERSION_CONFLICT"
        assert body["currentVersion"] == 2
        assert body["remoteChanges"] == []
    missing = await api_client.put(config_path(project.id), json={"body": {"overrides": {}}}, headers=headers_of(owner))
    assert missing.status_code == 428
    assert (await get_config(api_client, project.id, owner)).json()["revision"] == 2


async def test_rules_replace_config__C09_no_row(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Base > 0 khi chưa có dòng → 409 với `currentVersion` 0."""
    owner, project = await seed_admin_project(db_session)
    response = await put_config(api_client, project.id, owner, replace_body(3, _CONFIG))
    assert response.status_code == 409
    assert response.json()["currentVersion"] == 0


async def test_rules_replace_config__C09b(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Cùng người, cùng thân, `baseVersion = revision - 1` → 200, `revision` giữ nguyên, đúng một dòng nhật ký."""
    owner, project = await seed_admin_project(db_session)
    first = await put_config(api_client, project.id, owner, replace_body(0, _CONFIG))
    repeat = await put_config(api_client, project.id, owner, replace_body(0, _CONFIG))
    assert repeat.status_code == 200
    assert repeat.json() == first.json()
    assert (await _stored(db_sessionmaker, project.id)).revision == 1
    rows = await activity_rows(db_sessionmaker, actor_id=owner.id, kind=ActivityKind.RULES_CONFIG_UPDATE)
    assert len(rows) == 1


async def test_rules_replace_config__C09b_other_user(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Cùng thân, `baseVersion = revision - 1`, người khác (cũng admin) → 409; cùng người khác thân → 409."""
    owner = await make_user(db_session, role="admin")
    other = await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=owner, members=[other])
    await put_config(api_client, project.id, owner, replace_body(0, _CONFIG))
    assert (await put_config(api_client, project.id, other, replace_body(0, _CONFIG))).status_code == 409
    assert (await put_config(api_client, project.id, owner, replace_body(0, {}))).status_code == 409


async def test_rules_replace_config__C09b_hash_ignores_number_spelling(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """1200 và 1200.0 cùng một băm: gửi lặp bằng cách viết khác vẫn là C09b."""
    owner, project = await seed_admin_project(db_session)
    as_int = {"DOOR-WIDTH": {"thresholds": {"door.minWidthMm": 1200}}}
    as_float = {"DOOR-WIDTH": {"thresholds": {"door.minWidthMm": 1200.0}}}
    await put_config(api_client, project.id, owner, replace_body(0, as_int))
    repeat = await put_config(api_client, project.id, owner, replace_body(0, as_float))
    assert repeat.status_code == 200
    assert repeat.json()["revision"] == 1


async def test_rules_replace_config__C09b_stale_entry_filtered(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """PUT hợp lệ, chèn `OLD-RULE` bằng SQL rồi gửi lặp cùng thân (C09b) → 200 không có `OLD-RULE`."""
    owner, project = await seed_admin_project(db_session)
    await put_config(api_client, project.id, owner, replace_body(0, _CONFIG))
    await db_session.execute(
        text("UPDATE rule_configs SET overrides = overrides || CAST(:extra AS jsonb) WHERE project_id = :p"),
        {"extra": '{"OLD-RULE": {"enabled": false}}', "p": project.id},
    )
    await db_session.commit()
    repeat = await put_config(api_client, project.id, owner, replace_body(0, _CONFIG))
    assert repeat.status_code == 200
    assert "OLD-RULE" not in repeat.json()["overrides"]
    assert repeat.json()["overrides"] == _CONFIG


async def test_rules_replace_config__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Ghi thắng → đúng một dòng `rules.config_update` (actor = `sub`, nhãn = tên dự án); 409 không ghi thêm."""
    owner, project = await seed_admin_project(db_session)
    await put_config(api_client, project.id, owner, replace_body(0, _CONFIG))
    row = await assert_one_activity(
        db_sessionmaker, actor_id=owner.id, kind=ActivityKind.RULES_CONFIG_UPDATE, object_code=project.id
    )
    assert row.object_label == project.name
    assert row.project_id == project.id
    await put_config(api_client, project.id, owner, replace_body(0, {}))
    await assert_one_activity(
        db_sessionmaker, actor_id=owner.id, kind=ActivityKind.RULES_CONFIG_UPDATE, object_code=project.id
    )


async def test_rules_replace_config__wire_keeps_false_zero_and_case(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Dây: ngưỡng `0` và `enabled: false` có mặt; khoá `WALL-THICKNESS` giữ nguyên, không camelCase."""
    owner, project = await seed_admin_project(db_session)
    overrides = {
        "ESCAPE-DISTANCE": {"thresholds": {"escape.openingOnOutlineToleranceMm": 0}},
        "WALL-THICKNESS": {"enabled": False},
    }
    response = await put_config(api_client, project.id, owner, replace_body(0, overrides))
    assert response.json()["overrides"] == overrides
    assert response.json()["overrides"]["ESCAPE-DISTANCE"]["thresholds"]["escape.openingOnOutlineToleranceMm"] == 0
    assert "wallThickness" not in response.json()["overrides"]


async def test_rules_replace_config__cascade_on_project_delete(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Xoá cứng dự án (SQL trực tiếp) → dòng `rule_configs` mất (FK `ON DELETE CASCADE`)."""
    owner, project = await seed_admin_project(db_session)
    await put_config(api_client, project.id, owner, replace_body(0, _CONFIG))
    count = "SELECT count(*) FROM rule_configs"
    assert (await db_session.execute(text(count))).scalar_one() == 1
    await db_session.execute(text("DELETE FROM projects WHERE id = :p"), {"p": project.id})
    await db_session.commit()
    assert (await db_session.execute(text(count))).scalar_one() == 0


async def test_rules_replace_config__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`RuleOverride` chỉ có `thresholds` → response vắng `enabled`, `severity` (không `null`)."""
    owner, project = await seed_admin_project(db_session)
    overrides = {"WALL-LENGTH": {"thresholds": {"wall.minLengthMm": 100}}}
    response = await put_config(api_client, project.id, owner, replace_body(0, overrides))
    assert response.json()["overrides"]["WALL-LENGTH"] == {"thresholds": {"wall.minLengthMm": 100}}
