"""N3 `members_add_member` (B2-02 [2], [8]): C01 C02 C03 C06 C07 C08 C10 C11 C16 C17 C18 + case theo việc."""

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.core import extensions
from apps.api.project_members.settings import reset_project_members_settings_cache
from apps.api.project_members.tests.support import (
    SINKS_SUBMODULE,
    RecordingSink,
    add,
    headers_of,
    member_ids,
    members_path,
    seed_project,
    updated_at,
)
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.access import activity_rows, assert_one_activity


async def test_members_add_member__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Thêm mới: 201 `UserOut`, membership `added_by` = người gọi (K05), một dòng nhật ký `MEMBER_ADD`."""
    actor, target = await make_user(db_session, role="engineer"), await make_user(db_session, role="viewer")
    project = await seed_project(db_session, owner=actor)
    response = await add(api_client, actor, project, target.email)
    assert response.status_code == 201
    assert response.json() == {"id": target.id, "email": target.email, "name": target.name, "role": "viewer"}
    assert await member_ids(db_session, project.id) == sorted([actor.id, target.id])
    row = await assert_one_activity(
        db_sessionmaker, actor_id=actor.id, kind=ActivityKind.MEMBER_ADD, object_code=target.id
    )
    assert (row.project_id, row.object_label) == (project.id, target.email)


@pytest.mark.parametrize("bad_body", [{"email": 7}, {"email": None}, {}, []])
async def test_members_add_member__C02(api_client: httpx.AsyncClient, db_session: AsyncSession, bad_body: Any) -> None:
    """Thân sai kiểu hay thiếu email → 422 `VALIDATION`."""
    actor = await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=actor)
    response = await api_client.post(members_path(project.id), json=bad_body, headers=headers_of(actor))
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


async def test_members_add_member__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION` (strict)."""
    actor = await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=actor)
    body = {"email": "a@example.com", "role": "admin"}
    response = await api_client.post(members_path(project.id), json=body, headers=headers_of(actor))
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


async def test_members_add_member__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không là thành viên → 404 `project` (K08), không phải 403."""
    owner, outsider = await make_user(db_session, role="engineer"), await make_user(db_session, role="admin")
    target = await make_user(db_session)
    project = await seed_project(db_session, owner=owner)
    response = await add(api_client, outsider, project, target.email)
    assert response.status_code == 404
    assert response.json()["resource"] == "project"
    assert await member_ids(db_session, project.id) == [owner.id]


async def test_members_add_member__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Viewer là thành viên nhưng thiếu `project.settings.edit` → 403."""
    owner, viewer = await make_user(db_session, role="engineer"), await make_user(db_session, role="viewer")
    target = await make_user(db_session)
    project = await seed_project(db_session, owner=owner, members=[viewer])
    response = await add(api_client, viewer, project, target.email)
    assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")


async def test_members_add_member__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: Any
) -> None:
    """Dự án đã xoá mềm → 404 `project`."""
    owner, target = await make_user(db_session, role="admin"), await make_user(db_session)
    project = await seed_project(db_session, owner=owner, deleted_at=fake_clock.now())
    response = await add(api_client, owner, project, target.email)
    assert (response.status_code, response.json()["resource"]) == (404, "project")


async def test_members_add_member__C16(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Email khác hoa thường của người có sẵn → thêm đúng người đó, trả email đã lưu."""
    actor = await make_user(db_session, role="engineer")
    target = await make_user(db_session, email="Nguoi.Mau@Example.com")
    project = await seed_project(db_session, owner=actor)
    response = await add(api_client, actor, project, "  NGUOI.MAU@example.COM ")
    assert (response.status_code, response.json()["id"], response.json()["email"]) == (
        201,
        target.id,
        "Nguoi.Mau@Example.com",
    )


async def test_members_add_member__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Người chưa có ảnh → response không có khoá `avatarUrl` (K02)."""
    actor, target = await make_user(db_session, role="admin"), await make_user(db_session)
    project = await seed_project(db_session, owner=actor)
    body = (await add(api_client, actor, project, target.email)).json()
    assert "avatarUrl" not in body


async def test_members_add_member__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Nhật ký ghi `actor_id` = người gọi, `object_code` = người được thêm, `project_id` đúng."""
    actor, target = await make_user(db_session, role="admin"), await make_user(db_session)
    project = await seed_project(db_session, owner=actor)
    await add(api_client, actor, project, target.email)
    rows = await activity_rows(db_sessionmaker, kind=ActivityKind.MEMBER_ADD)
    assert [(r.actor_id, r.object_code, r.project_id) for r in rows] == [(actor.id, target.id, project.id)]


async def test_members_add_member__C11(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hạn mức đặt 3/10 s: lượt thứ 4 → 429 `RATE_LIMITED` + `Retry-After` ≤ 10."""
    monkeypatch.setenv("MEMBER_ADD_RATE_LIMIT", "3")
    monkeypatch.setenv("MEMBER_ADD_RATE_WINDOW_S", "10")
    reset_project_members_settings_cache()
    try:
        actor, target = await make_user(db_session, role="admin"), await make_user(db_session)
        project = await seed_project(db_session, owner=actor)
        for _ in range(3):
            assert (await add(api_client, actor, project, target.email)).status_code in (200, 201)
        blocked = await add(api_client, actor, project, target.email)
    finally:
        monkeypatch.delenv("MEMBER_ADD_RATE_LIMIT")
        monkeypatch.delenv("MEMBER_ADD_RATE_WINDOW_S")
        reset_project_members_settings_cache()
    assert (blocked.status_code, blocked.json()["code"]) == (429, "RATE_LIMITED")
    assert 0 < int(blocked.headers["retry-after"]) <= 10


async def test_members_add_member__C10_sink_once(
    api_client: httpx.AsyncClient, api_app: FastAPI, db_session: AsyncSession
) -> None:
    """Lặp khoá cùng thân → cùng response và **một** lượt sink; khác thân → 422 `IDEMPOTENCY_KEY_REUSED`."""
    sink = RecordingSink()
    extensions.override(api_app, SINKS_SUBMODULE, [("test", [sink])])
    actor = await make_user(db_session, role="admin")
    first_target, second_target = await make_user(db_session), await make_user(db_session)
    project = await seed_project(db_session, owner=actor)
    key = {"Idempotency-Key": "khoa-them-thanh-vien-01"}
    first = await add(api_client, actor, project, first_target.email, headers=key)
    second = await add(api_client, actor, project, first_target.email, headers=key)
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json() == second.json()
    assert [call["user_id"] for call in sink.calls] == [first_target.id]
    reused = await add(api_client, actor, project, second_target.email, headers=key)
    assert (reused.status_code, reused.json()["code"]) == (422, "IDEMPOTENCY_KEY_REUSED")
    assert len(sink.calls) == 1


async def test_members_add_member__pending_ok(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Người `pending` được thêm (không có trạng thái `invited`)."""
    actor = await make_user(db_session, role="admin")
    pending = await make_user(db_session, status="pending", password=None)
    project = await seed_project(db_session, owner=actor)
    assert (await add(api_client, actor, project, pending.email)).status_code == 201


async def test_members_add_member__unavailable_same_body(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Tài khoản `disabled` và email lạ cùng 422 `MEMBER_USER_UNAVAILABLE`, cùng thân (trừ `requestId`)."""
    actor = await make_user(db_session, role="admin")
    disabled = await make_user(db_session, status="disabled")
    project = await seed_project(db_session, owner=actor)
    bodies = []
    for email in (disabled.email, "khong-ton-tai@example.com"):
        response = await add(api_client, actor, project, email)
        assert (response.status_code, response.json()["code"]) == (422, "MEMBER_USER_UNAVAILABLE")
        bodies.append({k: v for k, v in response.json().items() if k != "requestId"})
    assert bodies[0] == bodies[1]
    assert bodies[0]["field"] == "email"


BAD_EMAILS = ["ánh@cty.vn", f"{chr(0x17F)}@example.com", f"{chr(0x212A)}@example.com", "khong-phai-email", ""]
"""Unicode, chữ s dài U+017F, dấu Kelvin U+212A, sai dạng."""


@pytest.mark.parametrize("email", BAD_EMAILS)
async def test_members_add_member__bad_email(
    api_client: httpx.AsyncClient, db_session: AsyncSession, email: str
) -> None:
    """Email ngoài `validate_wire_email` → 422 `VALIDATION` `field:"email"` (K37)."""
    actor = await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=actor)
    response = await add(api_client, actor, project, email)
    assert (response.status_code, response.json()["code"], response.json()["field"]) == (422, "VALIDATION", "email")


async def test_members_add_member__no_sink_installed(
    api_client: httpx.AsyncClient, api_app: FastAPI, db_session: AsyncSession
) -> None:
    """Chưa cài sink → 201, không lỗi."""
    extensions.override(api_app, SINKS_SUBMODULE, [])
    actor, target = await make_user(db_session, role="admin"), await make_user(db_session)
    project = await seed_project(db_session, owner=actor)
    assert (await add(api_client, actor, project, target.email)).status_code == 201


async def test_members_add_member__sink_raises_rolls_back(
    api_client: httpx.AsyncClient,
    api_app: FastAPI,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """Sink ném → không membership, không nhật ký (rollback cả lượt, lỗi không bị nuốt)."""
    sink = RecordingSink(fail=True)
    extensions.override(api_app, SINKS_SUBMODULE, [("test", [sink])])
    actor, target = await make_user(db_session, role="admin"), await make_user(db_session)
    project = await seed_project(db_session, owner=actor)
    response = await add(api_client, actor, project, target.email)
    assert (response.status_code, response.json()["code"]) == (500, "INTERNAL")
    assert len(sink.calls) == 1
    assert await member_ids(db_session, project.id) == [actor.id]
    assert await activity_rows(db_sessionmaker, kind=ActivityKind.MEMBER_ADD) == []


async def test_members_add_member__touches_project_only_when_new(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`project.updatedAt` đổi khi thêm mới; đã là thành viên → 200, không đổi."""
    actor, target = await make_user(db_session, role="admin"), await make_user(db_session)
    project = await seed_project(db_session, owner=actor)
    before = await updated_at(db_session, project.id)
    assert (await add(api_client, actor, project, target.email)).status_code == 201
    touched = await updated_at(db_session, project.id)
    assert touched != before
    again = await add(api_client, actor, project, target.email)
    assert (again.status_code, again.json()["id"]) == (200, target.id)
    assert await updated_at(db_session, project.id) == touched
